import json
from pathlib import Path

from xteink.docs import app


def generate_static_swagger(output_path: str = "web/api.html"):
    """
    Generates a single static HTML file containing the Swagger UI.
    Uses CDNs for Swagger assets to keep the file lightweight and portable.
    """
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    openapi_schema = json.dumps(app.openapi())

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Xteink API Reference</title>
    <link rel="stylesheet" type="text/css"
          href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" >
    <style>
      html {{ box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }}
      *, *:before, *:after {{ box-sizing: inherit; }}
      body {{ margin:0; background: #fafafa; }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"> </script>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"> </script>
    <script>
    window.onload = function() {{
      const ui = SwaggerUIBundle({{
        spec: {openapi_schema},
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "BaseLayout",
        persistAuthorization: true
      }});
      window.ui = ui;
    }};
    </script>
</body>
</html>
"""
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Static API documentation generated at: {out_file}")


if __name__ == "__main__":
    generate_static_swagger()
