# prompts.py
import json

def get_config_generation_prompt(title: str, context: str) -> str:
    """Prompt to generate the initial blog post configuration."""
    return f"""
    You are a strategic content creator for a freelance developer whose business is described below.

    ---
    BUSINESS CONTEXT:
    {context}
    ---

    Your task is to generate a configuration for a blog post based on the following title.

    TITLE: "{title}"

    Generate the following fields:
    1.  `title`: Use the exact title provided.
    2.  `topic`: A detailed paragraph on what the article will cover.
    3.  `keywords`: A JSON list of 10-12 highly relevant SEO keywords.
    4.  `target_audience`: A detailed paragraph describing the ideal reader for this article.
    5.  `azlo_strategic_angle`: A detailed paragraph on how this article connects to the business's core services.
    6.  `image_style`: A paragraph describing the visual style for the article's images.

    Respond ONLY with a valid JSON object. Do not include markdown fences (```json).
    Example: {{"title": "...", "topic": "...", "keywords": ["kw1"], "target_audience": "...", "azlo_strategic_angle": "...", "image_style": "..."}}
    """

def get_plan_generation_prompt(config: dict) -> str:
    """Prompt to generate the blog post outline and image plan."""
    # This function appears correct and does not need changes based on the logs.
    return f"""
You are a senior content strategist. Create a plan for a blog post based on the configuration below.

**Outline Structure:**
- `title`: The main title.
- `summary`: A concise, 2-3 sentence summary.
- `introduction_heading`: An H3 heading for the introduction.
- `introduction`: Paragraphs for the intro.
- `sections`: An array of objects, each with `title` (H2 heading) and `talking_points`.
- `conclusion`: A concluding section ending with a call to action linking to `https://azlo.pro/index.html#contact`.

**Image Plan:**
- An array of image objects.
- The first image MUST use the marker `[FEATURED_IMAGE_MARKER]`.
- Include at least two other in-content images with unique markers (e.g., `[IN_CONTENT_IMAGE_1_MARKER]`).
- Each object needs: `placement_marker`, `generation_prompt`, `alt_text`.

**CRITICAL INSTRUCTION:** Weave this strategic angle throughout the outline:
---
{config.get('article_idea', {}).get('azlo_strategic_angle', 'N/A')}
---

**Full Article Configuration:**
---
{json.dumps(config.get('article_idea', {}), indent=2)}
---

Respond ONLY with a valid JSON object containing `outline` and `image_plan` keys.
"""

def get_article_generation_prompt(plan: dict) -> str:
    """Prompt to generate the final article markdown from the plan."""
    # This function appears correct and does not need changes based on the logs.
    return f"""
You are a senior tech writer. Write a blog post in GitHub Flavored Markdown based *exactly* on the provided JSON plan.

**CRITICAL RULES:**
1.  **No H1 Title:** Do not write a main H1 title.
2.  **Featured Image First:** Start with the exact `placement_marker` for the featured image.
3.  **Summary Next:** After the marker, write the `summary` as plain text.
4.  **Structure:** Use `---` for a horizontal rule, `###` for the intro heading, and `##` for section titles.
5.  **Image Markers:** Where the plan suggests a visual, insert the *exact* `placement_marker` string (e.g., `[IN_CONTENT_IMAGE_1_MARKER]`). **DO NOT** generate Hugo shortcodes like `{{{{< figure >}}}}`.

**Article Plan (Source of Truth):**
---
{json.dumps(plan, indent=2)}
---
"""
