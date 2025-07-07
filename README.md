# 🤖 AI Automated Blogging Boilerplate

A free, open-source boilerplate for generating complete, SEO-friendly blog posts for a static site generator like Hugo. Just provide a list of titles, and the script does the rest—from writing the article to generating and placing images.

This project uses Google's Gemini and Imagen models via Vertex AI to create high-quality, strategically aligned content.

## ✨ Features

- **Automated Content Pipeline**: From a CSV of titles to complete Hugo page bundles.
- **Strategic Content Generation**: Uses a detailed business context to ensure content is aligned with your brand.
- **AI-Powered SEO**: Generates relevant keywords for each post.
- **Automated Image Generation**: Creates and places a featured image and in-content visuals.
- **Robust Error Handling**: Includes retries with exponential backoff for API calls and fallback placeholder images.
- **Highly Customizable**: All settings, from API models to business context and prompts, are in external configuration files.

## ⚙️ How It Works

The script follows a multi-step process for each title:
1.  **Configure**: Generates a strategic plan for the article (topic, keywords, angle).
2.  **Plan**: Creates a detailed outline and an image plan (prompts and placement).
3.  **Write**: Drafts the full article in Markdown based on the outline.
4.  **Generate Images**: Creates images using Vertex AI based on the plan.
5.  **Assemble**: Creates a Hugo page bundle (`index.md` + images) with the correct front matter and image shortcodes.

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.8+
- A Google Cloud Platform (GCP) project with Vertex AI enabled.
- Authenticated GCP credentials on your local machine (run `gcloud auth application-default login`).
- A Gemini API Key for the initial configuration step.

### 2. Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd ai-blog-boilerplate
    ```

2.  **Set up a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set your Gemini API Key:**
    The script requires a `GEMINI_API_KEY` for the initial config generation step.
    ```bash
    export GEMINI_API_KEY='YOUR_API_KEY_HERE'
    ```

### 3. Configuration

Open `config.yaml` and customize it for your project:

- **`gcp_project_id`**: Your Google Cloud Project ID.
- **`gcp_location`**: The GCP region for Vertex AI (e.g., `us-central1`).
- **`hugo_blog_path`**: The output path for the blog posts (e.g., `./content/posts`).
- **`models`**: Specify the text and image models you want to use.
- **`business_context`**: **This is critical.** Update this section with your business details to ensure the AI generates relevant, on-brand content.

### 4. Add Your Blog Titles

Edit `blog_titles.csv` and add the list of blog post titles you want to generate. The file should have a header row named `title`.

```csv
title
"How Custom Automation Beats Off-the-Shelf Tools"
"Why Go is the Perfect Choice for Your Next SaaS MVP"
"Unlocking Business Insights with Custom BI Dashboards"
```

### 5. Run the Script

Once everything is configured, start the content generation process:

```bash
python main.py
```

The script will process each title from the CSV, and you'll find the completed Hugo page bundles in the directory you specified in `hugo_blog_path`.

---

## 🔧 Customization

### Prompts

All AI prompts are located in `prompts.py`. You can edit these prompts to change the tone, style, or structure of the generated content without touching the core logic in `main.py`.

### Models

You can easily swap out the models used in `config.yaml`. Just ensure the models are available in your selected GCP location.