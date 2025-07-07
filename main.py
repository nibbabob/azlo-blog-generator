import os
import sys
import yaml
import json
import re
import logging
import time
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import google.generativeai as genai
from google.generativeai.client import configure
from PIL import Image, ImageDraw, ImageFont
from google.api_core import exceptions
import shutil

# --- New imports for the loading spinner ---
import threading
import itertools

# --- Vertex AI imports ---
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.vision_models import ImageGenerationModel

# --- Configuration Loader ---
def load_config(config_path='config.yaml') -> Dict:
    """Loads the configuration from a YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logging.info("Configuration loaded successfully from %s", config_path)
        return config
    except FileNotFoundError:
        logging.error("FATAL: Configuration file not found at %s. Please create it.", config_path)
        sys.exit(1)
    except Exception as e:
        logging.error("FATAL: Error loading configuration: %s", e)
        sys.exit(1)

# --- Global Configuration ---
CONFIG = load_config()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- NEW: Loading Spinner Class ---
class LoadingSpinner:
    """A context manager for showing a loading spinner in the console."""
    def __init__(self, text: str = "Loading...", delay: float = 0.1):
        self.spinner = itertools.cycle(['-', '/', '|', '\\'])
        self.delay = delay
        self.text = text
        self.busy = False
        self.thread = None

    def _spin(self):
        while self.busy:
            # Use \r (carriage return) to move cursor to the beginning of the line
            sys.stdout.write(f"\r{self.text} {next(self.spinner)}")
            sys.stdout.flush()
            time.sleep(self.delay)

    def __enter__(self):
        self.busy = True
        # The spinner runs on a separate thread
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.busy = False
        # Add a check to ensure the thread was successfully created
        if self.thread is not None:
            self.thread.join()
        
        # Clear the spinner line and move cursor to the beginning
        sys.stdout.write('\r' + ' ' * (len(self.text) + 2) + '\r')
        sys.stdout.flush()
        
        # If an exception occurred, it will be re-raised
        return False

# --- Helper Functions ---
def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'[^\w\-]', '', text)
    text = text.strip('-')
    return text

def create_placeholder_image(prompt: str, output_path: str):
    """Create a placeholder image when API generation fails."""
    width, height = 1200, 630
    try:
        img = Image.new('RGB', (width, height), color=(26, 26, 26))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 30)
        except IOError:
            font = ImageFont.load_default()

        # Simple text wrapping
        words = prompt.split()
        lines = ["FALLBACK (API Error/Refusal):", ""]
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 < 60: # Character limit per line
                current_line += f" {word}"
            else:
                lines.append(current_line.strip())
                current_line = word
        lines.append(current_line.strip())

        y_text = (height - (len(lines) * 40)) / 2
        for i, line in enumerate(lines):
            # Use getbbox for accurate width and height calculation
            left, top, right, bottom = font.getbbox(line)
            text_width = right - left
            
            # Center the text accurately
            draw.text(((width - text_width) / 2, y_text + i * 45), line, font=font, fill=(255, 100, 100))
        img.save(output_path, "JPEG")
        logging.info(f"Successfully created placeholder image: {output_path}")
    except Exception as e:
        logging.error(f"Failed to create placeholder image {output_path}: {e}", exc_info=True)
        raise

# --- Configuration Generation ---
def generate_blog_config(title: str) -> Optional[dict]:
    """Generate blog configuration using the model specified in config."""
    logging.info(f"🤖 Generating config for title: '{title}'...")
    # --- USES CONFIG ---
    model_name = CONFIG['models']['config_generation_model']
    context = CONFIG['azlo_pro_context']
    model = GenerativeModel(model_name)

    prompt_template = f"""
    You are a strategic content creator for a freelance developer whose business is described below.
    BUSINESS CONTEXT:
    ---
    {context}
    ---
    Your task is to generate the content for a blog post configuration based on the TITLE: "{title}"
    Generate the following fields: `title`, `topic`, `keywords` (JSON list), `azlo_strategic_angle`, `image_style`.
    Ensure `topic`, `azlo_strategic_angle`, and `image_style` are single continuous paragraphs.
    Respond ONLY with a valid JSON object. Example: {{"title": "...", "topic": "...", "keywords": ["kw1", "kw2"], "azlo_strategic_angle": "...", "image_style": "..."}}
    """
    try:
        response = model.generate_content(prompt_template)
        cleaned_json = re.sub(r'```json\n?|```', '', response.text).strip()
        return json.loads(cleaned_json)
    except (json.JSONDecodeError, Exception) as e:
        logging.error(f"Error generating config: {e}")
        return None

# --- Blog Generation Functions ---
def generate_plan(config: dict) -> dict:
    """Generate blog outline and image plan."""
    # --- USES CONFIG ---
    model_name = CONFIG['models']['text_model_name']
    logging.info(f"Generating outline using '{model_name}'...")
    model = GenerativeModel(model_name)

    base_prompt = """
    You are a senior content strategist for Azlo.pro. Create a plan for a blog post.
    **Outline Structure:** `title`, `summary`, `introduction_heading`, `introduction`, `sections` (array of {title, talking_points}), `conclusion`.
    The `conclusion` MUST end with a markdown link: `[contact Azlo.pro to discuss your project](https://azlo.pro/index.html#contact)`.
    **Image Plan Structure:** An array of {`placement_marker`, `generation_prompt`, `alt_text`}.
    The first image marker MUST be `[FEATURED_IMAGE_MARKER]`. Include at least two other unique markers like `[IN_CONTENT_IMAGE_1_MARKER]`.
    **Output:** Respond ONLY with a single, valid JSON object with `outline` and `image_plan` keys.
    """
    strategic_angle = config.get('article_idea', {}).get('azlo_strategic_angle')
    strategic_instruction = f"CRITICAL INSTRUCTION: Weave this strategic angle throughout the content:\n---\n{strategic_angle}\n---" if strategic_angle else ""
    prompt = f"{base_prompt}\n{strategic_instruction}\nFull Article Configuration:\n---\n{yaml.dump(config['article_idea'])}\n---"

    try:
        response = model.generate_content(prompt)
        cleaned_response_text = re.sub(r'```json\n?|```', '', response.text).strip()
        plan = json.loads(cleaned_response_text)
        if "outline" not in plan or "image_plan" not in plan:
            raise ValueError("Generated plan is missing 'outline' or 'image_plan'.")
        logging.info("Outline and image plan generated successfully.")
        return plan
    except Exception as e:
        logging.error(f"Error generating plan: {e}", exc_info=True)
        raise

def generate_article_text(plan: dict) -> str:
    """Generate article markdown content."""
    # --- USES CONFIG ---
    model_name = CONFIG['models']['text_model_name']
    logging.info(f"Generating article Markdown using '{model_name}'...")
    model = GenerativeModel(model_name)

    prompt = f"""
    You are a senior tech writer for Azlo.pro. Write a complete blog post in GitHub Flavored Markdown based *exactly* on the provided JSON plan.
    **CRITICAL RULES:**
    1.  **No Main Title:** Do NOT write a main H1 title ('#').
    2.  **Start with Featured Image:** The response MUST start with the featured image's `placement_marker`.
    3.  **Summary Next:** After the marker, write the `summary` as plain text (no blockquotes).
    4.  **Structure:** Use '---' after the summary, H3 ('###') for the intro heading, and H2 ('##') for section titles.
    5.  **Place Markers:** You MUST insert the *exact* `placement_marker` strings (e.g., `[IN_CONTENT_IMAGE_1_MARKER]`) from the plan where visuals are needed. DO NOT generate Hugo shortcodes like `{{{{< figure >}}}}`.
    **Article Plan (Your Source of Truth):**
    ---
    {json.dumps(plan, indent=2)}
    ---
    """
    try:
        response = model.generate_content(prompt)
        logging.info("Article Markdown generated successfully.")
        return response.text
    except Exception as e:
        logging.error(f"Failed to generate article text: {e}", exc_info=True)
        raise

def generate_single_image_api_call(prompt: str, output_path: str) -> bool:
    """Generate a single image using Vertex AI with retry logic from config."""
    # --- USES CONFIG ---
    gcp_project_id = CONFIG['vertex_ai']['gcp_project_id']
    gcp_location = CONFIG['vertex_ai']['gcp_location']
    model_name = CONFIG['models']['image_model_name']
    max_retries = CONFIG['api']['max_retries']
    initial_backoff = CONFIG['api']['initial_backoff_seconds']

    for attempt in range(max_retries):
        try:
            logging.info(f"Requesting image (Attempt {attempt + 1}/{max_retries}): '{prompt[:50]}...'")
            model = ImageGenerationModel.from_pretrained(model_name)
            response = model.generate_images(prompt=prompt, number_of_images=1)
            response[0].save(location=output_path, include_generation_parameters=True)

            with Image.open(output_path) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(output_path, "JPEG", quality=85)
            logging.info(f"Successfully generated and saved image to {output_path}")
            return True
        except exceptions.ResourceExhausted as e:
            logging.warning(f"Quota exceeded. Retrying after delay...")
            if attempt < max_retries - 1:
                delay = initial_backoff * (2 ** attempt)
                time.sleep(delay)
            else:
                logging.error(f"Image generation failed after {max_retries} attempts: {e}")
                return False
        except Exception as e:
            logging.error(f"Unexpected error during image generation: {e}", exc_info=True)
            return False
    return False

def generate_images(plan: dict) -> dict:
    """Generate all images for the blog post."""
    logging.info("Generating images...")
    image_filepaths = {}
    # --- USES CONFIG ---
    temp_dir = Path(CONFIG['paths']['temp_image_dir'])
    api_call_delay = CONFIG['api']['call_delay_seconds']
    temp_dir.mkdir(exist_ok=True)

    # Create stable filenames
    filename_map, in_content_count = {}, 1
    markers = [spec['placement_marker'] for spec in plan['image_plan']]
    featured_marker = next((m for m in markers if "featured" in m.lower()), None)
    if featured_marker:
        filename_map[featured_marker] = "featured_image.jpg"
    for marker in (m for m in markers if m != featured_marker):
        filename_map[marker] = f"image_{in_content_count}.jpg"
        in_content_count += 1

    for i, image_spec in enumerate(plan['image_plan']):
        marker, prompt = image_spec['placement_marker'], image_spec['generation_prompt']
        filename = filename_map.get(marker, f"image_extra_{i}.jpg")
        output_path = temp_dir / filename
        logging.info(f"Processing image {i+1}/{len(plan['image_plan'])} ('{filename}')...")
        if not generate_single_image_api_call(prompt, str(output_path)):
            logging.warning(f"API failed. Creating placeholder for '{filename}'.")
            create_placeholder_image(prompt, str(output_path))
        image_filepaths[marker] = str(output_path)
        if i < len(plan['image_plan']) - 1:
            logging.info(f"Waiting {api_call_delay} seconds...")
            time.sleep(api_call_delay)
    return image_filepaths

def assemble_bundle(hugo_path: str, article_idea: dict, plan: dict, article_md: str, image_paths: dict):
    """Assemble the Hugo page bundle."""
    logging.info("Assembling Hugo Page Bundle...")
    title = plan['outline'].get('title', article_idea.get('title', 'Untitled Post'))
    unique_slug = f"{slugify(title)}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    bundle_path = Path(hugo_path) / unique_slug
    bundle_path.mkdir(parents=True, exist_ok=True)
    logging.info(f"Created bundle directory: {bundle_path}")

    # Move images and update paths
    final_image_paths = {}
    for marker, temp_path_str in image_paths.items():
        temp_path = Path(temp_path_str)
        if temp_path.exists():
            dest_path = bundle_path / temp_path.name
            shutil.move(str(temp_path), str(dest_path))
            final_image_paths[marker] = temp_path.name

    # Clean up temp directory
    temp_dir = Path(CONFIG['paths']['temp_image_dir'])
    if temp_dir.exists() and not any(temp_dir.iterdir()):
        shutil.rmtree(temp_dir)

    # Create front matter
    featured_filename = next((name for marker, name in final_image_paths.items() if "featured" in marker.lower()), None)
    front_matter = {'title': title, 'date': datetime.now().astimezone().isoformat(), 'summary': plan['outline'].get('summary'), 'keywords': article_idea.get('keywords', [])}
    if featured_filename:
        front_matter['image'] = featured_filename
        try:
            shutil.copyfile(bundle_path / featured_filename, bundle_path / "og_image.jpg")
            front_matter['og_image'] = "og_image.jpg"
        except Exception as e:
            logging.error(f"Error creating OG image: {e}")

    # Replace markers with Hugo shortcodes
    content_with_figures = article_md
    for marker, filename in final_image_paths.items():
        alt_text = next((s['alt_text'] for s in plan['image_plan'] if s['placement_marker'] == marker), "")
        hugo_shortcode = f'\n\n{{{{< figure src="{filename}" alt="{alt_text}" >}}}}\n\n'
        content_with_figures = content_with_figures.replace(marker, hugo_shortcode)

    # Write index.md
    with open(bundle_path / "index.md", 'w', encoding='utf-8') as f:
        f.write("---\n")
        yaml.dump(front_matter, f, allow_unicode=True, sort_keys=False)
        f.write("---\n")
        f.write(content_with_figures)
    logging.info(f"Successfully created {bundle_path / 'index.md'}")

# --- UPDATED: Process Single Title with Loading Spinner ---
def process_single_title(title: str, hugo_posts_path: str):
    """Process a single blog title through the entire pipeline with loading visuals."""
    try:
        call_delay = CONFIG['api']['call_delay_seconds']

        with LoadingSpinner("Step 1/5: Generating strategic configuration..."):
            article_idea = generate_blog_config(title)
        if not article_idea:
            raise ValueError("Failed to generate article idea config.")
        full_config = {'article_idea': article_idea, 'hugo_posts_path': hugo_posts_path}
        time.sleep(call_delay)

        with LoadingSpinner("Step 2/5: Creating article outline and image plan..."):
            plan = generate_plan(full_config)
        time.sleep(call_delay)

        with LoadingSpinner("Step 3/5: Writing article Markdown..."):
            article_markdown = generate_article_text(plan)
        time.sleep(call_delay)

        # The generate_images function logs its own progress for each image,
        # which will appear below the main spinner line.
        with LoadingSpinner("Step 4/5: Generating all images..."):
            image_filenames = generate_images(plan)

        with LoadingSpinner("Step 5/5: Assembling Hugo page bundle..."):
            assemble_bundle(hugo_posts_path, article_idea, plan, article_markdown, image_filenames)

        logging.info(f"✅ Successfully processed: {title}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to process '{title}': {e}", exc_info=True)
        return False

def load_titles_from_csv(csv_path: str) -> List[str]:
    """Load titles from CSV file, assuming title is in the first column."""
    titles = []
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            for row in reader:
                if row and row[0].strip():
                    titles.append(row[0].strip())
        logging.info(f"Loaded {len(titles)} titles from {csv_path}")
        return titles
    except FileNotFoundError:
        logging.error(f"CSV file not found: {csv_path}")
        return []
    except Exception as e:
        logging.error(f"Error reading CSV {csv_path}: {e}")
        return []

def main():
    """Main function to run the blog generation process."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\nERROR: GEMINI_API_KEY environment variable not found.")
        sys.exit(1)
    configure(api_key=api_key)

    try:
        gcp_project_id = CONFIG['vertex_ai']['gcp_project_id']
        gcp_location = CONFIG['vertex_ai']['gcp_location']
        vertexai.init(project=gcp_project_id, location=gcp_location)
        logging.info("Vertex AI initialized successfully for project %s", gcp_project_id)
    except Exception as e:
        logging.error("FATAL: Could not initialize Vertex AI. Please check your config. %s", e)
        sys.exit(1)

    # --- USES CONFIG ---
    csv_path = sys.argv[1] if len(sys.argv) > 1 else CONFIG['paths']['default_csv_path']
    hugo_path = sys.argv[2] if len(sys.argv) > 2 else CONFIG['paths']['hugo_posts_path']
    interval = CONFIG['api']['interval_between_posts_seconds']

    print(f"\n🚀 CSV Blog Generator for Hugo")
    print(f"   - CSV File: {csv_path}")
    print(f"   - Hugo Blog Path: {hugo_path}")
    print(f"   - Interval between posts: {interval} seconds\n")

    titles = load_titles_from_csv(csv_path)
    if not titles:
        print("No titles found. Exiting.")
        sys.exit(1)

    successful, failed = 0, 0
    for i, title in enumerate(titles, 1):
        print(f"\n{'='*60}\nProcessing {i}/{len(titles)}: {title}\n{'='*60}\n")
        if process_single_title(title, hugo_path):
            successful += 1
        else:
            failed += 1
        if i < len(titles):
            print(f"\n⏳ Waiting {interval} seconds before next post...")
            time.sleep(interval)

    print(f"\n{'='*60}\n🎉 Processing Complete!")
    print(f"✅ Successful: {successful} | ❌ Failed: {failed}")
    print(f"📁 Blog posts saved to: {hugo_path}\n{'='*60}\n")

if __name__ == "__main__":
    main()