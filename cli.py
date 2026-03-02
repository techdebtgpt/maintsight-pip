#!/usr/bin/env python3
"""
MaintSight CLI - AI-powered maintenance risk predictor for git repositories.
"""

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv(verbose=True)

import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from models import RiskCategory

# Import modules
from services import FeatureEngineer, GitCommitCollector, XGBoostPredictor
from utils.logger import Logger


@click.group()
@click.version_option(version="0.1.0", prog_name="maintsight")
def main():
    """MaintSight - AI-powered maintenance risk predictor for git repositories."""
    pass


def _add_to_gitignore(repo_path: str) -> None:
    """Add .maintsight/ to .gitignore if not already present."""
    try:
        gitignore_path = Path(repo_path) / ".gitignore"
        maintsight_entry = ".maintsight/"

        # Read existing .gitignore content
        gitignore_content = ""
        try:
            gitignore_content = gitignore_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            # .gitignore doesn't exist, we'll create it
            pass

        # Check if .maintsight/ is already in .gitignore
        if ".maintsight" not in gitignore_content:
            # Add .maintsight/ to .gitignore
            new_content = (
                f"{gitignore_content.rstrip()}\n\n# MaintSight reports\n{maintsight_entry}\n"
                if gitignore_content
                else f"# MaintSight reports\n{maintsight_entry}\n"
            )
            gitignore_path.write_text(new_content, encoding="utf-8")
            print("   📝 Added .maintsight/ to .gitignore")
    except Exception as error:
        # Silently fail - not critical functionality
        print(f"   ⚠️  Could not update .gitignore ({error})")


def _save_html_report(
    predictions, commit_data, repo_path: str, run_id: Optional[str] = None
) -> Optional[str]:
    """Save HTML report to .maintsight directory and return file path."""
    try:
        # Resolve the absolute path first
        repo_path_abs = Path(repo_path).resolve()
        repo_name = repo_path_abs.name
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

        # Create .maintsight directory
        maintsight_dir = repo_path_abs / ".maintsight"
        maintsight_dir.mkdir(exist_ok=True)

        # Create HTML filename with repo name and timestamp
        html_filename = f"{repo_name}-{timestamp}.html"
        html_path = maintsight_dir / html_filename

        # Generate and save HTML content (with run_id for database integration)
        html_content = _format_html_report(
            predictions, repo_name, commit_data, repo_path, run_id
        )
        html_path.write_text(html_content, encoding="utf-8")

        print(f"HTML report saved to: {html_path}")
        return str(html_path.resolve())  # Return absolute path
    except Exception as error:
        print(f"Warning: Could not save HTML report: {error}")
        return None


def _open_html_report(html_path: str) -> None:
    """Auto-open HTML report in default browser and show clickable URL."""
    if not html_path:
        return

    # Ensure absolute path for file URL
    abs_path = Path(html_path).resolve()
    file_url = f"file://{abs_path}"
    relative_path = os.path.relpath(html_path)

    # Check platform and terminal for URL display
    is_mac = platform.system() == "Darwin"
    is_iterm2 = os.environ.get("TERM_PROGRAM") == "iTerm.app"
    is_apple_terminal = os.environ.get("TERM_PROGRAM") == "Apple_Terminal"

    print("\n🌐 Interactive HTML report generated!")
    print(f"   📁 File: {relative_path}")
    print("   💡 Opening in browser automatically...")

    # Determine open command based on platform
    if platform.system() == "Darwin":
        open_cmd = "open"
    elif platform.system() == "Windows":
        open_cmd = "start"
    else:
        open_cmd = "xdg-open"

    try:
        # Auto-open in default browser
        subprocess.run([open_cmd, file_url], check=True, capture_output=True)
        print("   ✅ Report opened in browser")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: show URL for manual copy-paste
        print("   ⚠️  Auto-open failed, use manual link below:")

        if is_mac and (is_iterm2 or is_apple_terminal):
            # Show clickable link for supported terminals
            print(f"   🌐 Browser: \x1b]8;;{file_url}\x1b\\{file_url}\x1b]8;;\x1b\\")
            print("   💡 Cmd+click the link above to open")
        else:
            # Plain URL for all other cases
            print(f"   🌐 Browser: {file_url}")
            print("   💡 Copy & paste the URL above in your browser")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("-b", "--branch", default="main", help="Git branch to analyze")
@click.option(
    "-mode",
    "--mode",
    type=click.Choice(["conservative", "moderate", "aggressive"]),
    default="moderate",
    help="Post-processing mode",
)
@click.option(
    "-model",
    "--model",
    type=click.Path(exists=True),
    default="models/xgboost_model.pkl",
    help="Path to XGBoost model file",
)
@click.option(
    "-metadata",
    "--metadata",
    type=click.Path(exists=True),
    default="models/xgboost_model_metadata.json",
    help="Path to XGBoost model metadata file",
)
@click.option("-o", "--output", type=click.Path(), help="Output file path")
@click.option(
    "-f",
    "--format",
    type=click.Choice(["json", "csv", "markdown", "html"]),
    default="html",
    help="Output format",
)
@click.option(
    "-t",
    "--threshold",
    type=float,
    default=0.0,
    help="Only show files above normalized score threshold (0-10)",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
def predict(
    path: str,
    branch: str,
    mode: str,
    model: str,
    metadata: str,
    output: Optional[str],
    format: str,
    threshold: float,
    verbose: bool,
):
    """Run maintenance risk predictions on a git repository."""

    logger = Logger("MaintSight")

    try:
        if verbose:
            logger.info(f"Analyzing git history (branch: {branch})...", "🔄")

        if verbose:
            logger.info("Running enhanced predictions...", "🤖")

        # Use clean enhanced prediction workflow
        try:
            if verbose:
                logger.info("Using enhanced prediction services", "🚀")

            # Initialize services
            predictor = XGBoostPredictor(model_path=model, metadata_path=metadata)
            model_obj, metadata_dict = predictor.load_model()

            if verbose:
                logger.info(f"Loaded model v{metadata_dict['version']}", "🤖")
                logger.info(
                    f"Using enhanced features ({len(metadata_dict['feature_list'])} features)",
                    "🔧",
                )
                # Collect git data
            collector = GitCommitCollector(
                repo_path=path,
                branch=branch,
                window_size_days=150,
                only_existing_files=True,
            )

            commit_data = collector.fetch_commit_data()
            # Extract features using FeatureEngineer service
            features_df = FeatureEngineer.extract_features(
                path, branch, metadata_dict["feature_list"]
            )

            if verbose:
                logger.info(f"Extracted features for {len(features_df)} files", "📁")

            # Run predictions using XGBoostPredictor service
            predictions = predictor.predict_as_objects(features_df, mode)

            if verbose:
                logger.info("Applied enhanced post-processing", "✨")

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            if verbose:
                import traceback

                traceback.print_exc()
            sys.exit(1)

        # Filter by threshold (0-10 scale)
        if threshold > 0:
            predictions = [p for p in predictions if p.normalized_score >= threshold]

        if verbose:
            logger.success(
                f"Predictions complete: {len(predictions)} files analyzed", "✅"
            )

        # Format output
        if format == "json":
            output_data = []
            for pred in predictions:
                output_data.append(
                    {
                        "module": pred.module,
                        "risk_level": pred.risk_category.display_name,
                        "normalized_score": round(
                            pred.normalized_score, 2
                        ),  # 0-10 score
                        "raw_prediction": round(pred.raw_prediction, 4),
                        "risk_category": pred.risk_category.value,
                    }
                )
            result = json.dumps(output_data, indent=2)

        elif format == "csv":
            lines = ["module,risk_level,normalized_score,raw_prediction,risk_category"]
            for pred in predictions:
                lines.append(
                    f'"{pred.module}",{pred.risk_category.display_name},'
                    f"{pred.normalized_score:.2f},{pred.raw_prediction:.4f},{pred.risk_category.value}"
                )
            result = "\n".join(lines)

        elif format == "markdown":
            result = _format_markdown_report(predictions, Path(path).name)

        elif format == "html":
            result = _format_html_report(
                predictions, Path(path).name, commit_data, str(Path(path).resolve())
            )
        else:
            # Default to HTML format if unknown format is specified
            result = _format_html_report(
                predictions, Path(path).name, commit_data, str(Path(path).resolve())
            )

        # Save to central database first to get run_id for HTML
        run_id = None
        try:
            from utils.database_client import get_database_client

            db_client = get_database_client()
            if db_client.is_connected:
                run_id = db_client.save_prediction_run(
                    repository_path=str(Path(path).resolve()),
                    predictions=predictions,
                    commit_data=commit_data,
                    metadata=metadata_dict,
                    processing_mode=mode,
                    features_df=features_df,  # Pass the features DataFrame
                )
                if run_id and verbose:
                    logger.success(
                        f"Predictions saved to central database (Run ID: {run_id})",
                        "💾",
                    )
        except ImportError:
            if verbose:
                logger.info(
                    "Database client not available - install requests package for database integration",
                    "⚠️",
                )
        except Exception as e:
            if verbose:
                logger.info(f"Could not save to central database: {e}", "⚠️")

        # Generate HTML report with database integration
        resolved_path = str(Path(path).resolve())
        html_path = _save_html_report(predictions, commit_data, resolved_path, run_id)

        # Add .maintsight/ to .gitignore if not already present
        _add_to_gitignore(path)

        # Output results to specified file if requested
        if output:
            with open(output, "w") as f:
                f.write(result)
            logger.success(f"Results saved to: {output}", "✅")
        else:
            # For non-HTML formats, print to stdout
            if format != "html":
                print(result)

        # Always show the HTML report link and auto-open
        if html_path:
            _open_html_report(html_path)

        # Show summary
        if verbose:
            _show_summary(predictions, logger)

    except Exception as e:
        logger.error(f"Error: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


def _format_markdown_report(predictions, repo_name: str) -> str:
    """Format predictions as markdown report."""
    from datetime import datetime

    # Sort by normalized score (0-10)
    sorted_preds = sorted(predictions, key=lambda p: p.normalized_score, reverse=True)

    # Calculate distribution
    dist = {}
    for pred in predictions:
        category = pred.risk_category.value
        dist[category] = dist.get(category, 0) + 1

    total = len(predictions)

    report = f"""# MaintSight - Maintenance Risk Analysis Report

**Repository:** {repo_name}
**Date:** {datetime.now().isoformat()}
**Files Analyzed:** {total}

## Risk Distribution

| Risk Level | Count | Percentage |
|------------|-------|------------|
| Critical | {dist.get("critical", 0)} | {(dist.get("critical", 0) / total * 100):.1f}% |
| High | {dist.get("high", 0)} | {(dist.get("high", 0) / total * 100):.1f}% |
| Medium | {dist.get("medium", 0)} | {(dist.get("medium", 0) / total * 100):.1f}% |
| Low | {dist.get("low", 0)} | {(dist.get("low", 0) / total * 100):.1f}% |

## Top 20 High-Risk Files

| File | Risk Level | Normalized Score | Raw Score | Category |
|------|------------|------------------|-----------|----------|
"""

    for pred in sorted_preds[:20]:
        report += f"| `{pred.module}` | {pred.risk_category.display_name} | {pred.normalized_score:.2f} | {pred.raw_prediction:.4f} | {pred.risk_category.value} |\n"

    report += """
## Risk Categories

- **Critical Risk (9.0-10.0)**: Immediate action required - critical maintenance issues
- **High Risk (7.0-8.9)**: Moderate degradation - consider refactoring
- **Medium Risk (5.0-6.9)**: Some attention needed - monitor for issues
- **Low Risk (0.0-4.9)**: Good code quality - minimal maintenance needed

---
*Generated by MaintSight using XGBoost*
"""

    return report


def _generate_commit_stats_sections(predictions, commit_data):
    """Generate the commit statistics, file type distribution, and contributors sections."""
    if commit_data is None or len(commit_data) == 0:
        return ""

    # Get actual repository commit count (not sum of per-file commits)
    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    total_commits = int(result.stdout.strip())

    # Get actual repository bug fix commit count
    result = subprocess.run(
        ["git", "log", "--pretty=format:%s"], capture_output=True, text=True, check=True
    )
    messages = result.stdout.strip().split("\n") if result.stdout.strip() else []
    bug_commits = sum(
        1
        for msg in messages
        if any(kw in msg.lower() for kw in ["fix", "bug", "patch", "hotfix"])
    )

    # Calculate file-level statistics for avg commits per file
    if hasattr(commit_data, "iterrows"):
        # It's a pandas DataFrame
        file_commits = commit_data["commits"].sum()
    else:
        # It's a list of objects
        file_commits = sum(getattr(row, "commits", 0) for row in commit_data)

    avg_commits_per_file = (
        file_commits / len(commit_data) if len(commit_data) > 0 else 0
    )
    bug_fix_rate = (bug_commits / total_commits * 100) if total_commits > 0 else 0

    # File type distribution
    from pathlib import Path

    file_types = {}
    for pred in predictions:
        ext = Path(pred.module).suffix.lower() or ".no-ext"
        file_types[ext] = file_types.get(ext, 0) + 1

    top_file_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:8]

    # Average risk by file type
    risk_by_type = {}
    for pred in predictions:
        ext = Path(pred.module).suffix.lower() or ".no-ext"
        if ext not in risk_by_type:
            risk_by_type[ext] = {"sum": 0, "count": 0}
        risk_by_type[ext]["sum"] += pred.normalized_score
        risk_by_type[ext]["count"] += 1

    avg_risk_by_type = [
        (ext, data["sum"] / data["count"], data["count"])
        for ext, data in risk_by_type.items()
    ]
    avg_risk_by_type.sort(key=lambda x: x[1], reverse=True)

    # Get unique authors from all files
    all_authors = set()
    try:
        if hasattr(commit_data, "iterrows"):
            # It's a pandas DataFrame
            for _, row in commit_data.iterrows():
                if "author_names" in row and row["author_names"] is not None:
                    if isinstance(row["author_names"], list):
                        for author in row["author_names"]:
                            if author and str(author).strip():
                                all_authors.add(str(author).strip())
                    elif (
                        isinstance(row["author_names"], str)
                        and row["author_names"].strip()
                    ):
                        all_authors.add(row["author_names"].strip())
        else:
            # It's a list of objects/dicts
            for row in commit_data:
                if isinstance(row, dict):
                    author_names = row.get("author_names", None)
                else:
                    author_names = getattr(row, "author_names", None)

                if author_names:
                    if isinstance(author_names, list):
                        for author in author_names:
                            if author and str(author).strip():
                                all_authors.add(str(author).strip())
                    elif isinstance(author_names, str) and author_names.strip():
                        all_authors.add(author_names.strip())
    except Exception:
        # If we can't extract authors, continue with empty set
        pass

    authors_list = sorted(list(all_authors))

    return f"""
        <div class="two-column">
            <div class="section">
                <h2 class="commit-stats">💻 Commit Statistics</h2>
                <ul class="stat-list">
                    <li>
                        <span>Total Commits</span>
                        <span><strong>{total_commits}</strong></span>
                    </li>
                    <li>
                        <span>Total Authors</span>
                        <span><strong>{len(authors_list)}</strong></span>
                    </li>
                    <li>
                        <span>Bug Fix Commits</span>
                        <span><strong>{bug_commits}</strong></span>
                    </li>
                    <li>
                        <span>Avg Commits/File</span>
                        <span><strong>{avg_commits_per_file:.1f}</strong></span>
                    </li>
                    <li>
                        <span>Bug Fix Rate</span>
                        <span><strong>{bug_fix_rate:.1f}%</strong></span>
                    </li>
                </ul>
            </div>
            <div class="section">
                <h2 class="file-types">📁 File Type Distribution</h2>
                <ul class="stat-list">
                    {
        chr(10).join(
            [
                f'''<li>
                        <span class="file-type">{ext}</span>
                        <span><strong>{count}</strong> files</span>
                    </li>'''
                for ext, count in top_file_types
            ]
        )
    }
                </ul>
            </div>
        </div>

        <div class="section">
            <h2 class="commit-stats">👥 Repository Contributors ({
        len(authors_list) if authors_list else "Unknown"
    })</h2>
            <div class="authors-grid">
                {
        chr(10).join(
            [
                f'''<div class="author-item">
                    <div class="author-avatar">{author[0].upper()}</div>
                    <div class="author-name">{author}</div>
                </div>'''
                for author in (authors_list[:20] if authors_list else [])
            ]
        )
    }
            </div>
        </div>

        {
        '<div class="section">'
        + chr(10)
        + '    <h2 class="file-types">📊 Average Risk by File Type</h2>'
        + chr(10)
        + '    <ul class="stat-list">'
        + chr(10)
        + chr(10).join(
            [
                "<li>"
                + chr(10)
                + f'    <span class="file-type">{ext}</span>'
                + chr(10)
                + '    <span style="display: flex; align-items: center; gap: 10px;">'
                + chr(10)
                + f'        <span class="risk-score {("risk-high" if avg >= 0.2 else "risk-medium" if avg >= 0.1 else "risk-low" if avg >= 0.0 else "risk-good")}">{avg:.3f}</span>'
                + chr(10)
                + f"        <span><strong>{count}</strong> files</span>"
                + chr(10)
                + "    </span>"
                + chr(10)
                + "</li>"
                for ext, avg, count in avg_risk_by_type[:8]
            ]
        )
        + chr(10)
        + "    </ul>"
        + chr(10)
        + "</div>"
        if avg_risk_by_type
        else ""
    }
    """


def _format_html_report(
    predictions,
    repo_name: str,
    commit_data=None,
    repository_path: Optional[str] = None,
    run_id: Optional[str] = None,
) -> str:
    """Format predictions as interactive HTML report with database integration."""

    import json
    import os

    # Get API URL and repository path
    api_base_url = os.getenv("MAINTSIGHT_API_URL", "http://localhost:8000")
    if repository_path is None:
        repository_path = os.getcwd()

    # Get predictions with database IDs if run_id is available
    predictions_with_db_ids = None
    if run_id:
        try:
            from utils.database_client import get_predictions_with_database_ids

            predictions_with_db_ids = get_predictions_with_database_ids(run_id)
        except Exception:
            pass

    # Calculate statistics
    total_files = len(predictions)
    critical = len(
        [p for p in predictions if p.risk_category.value == RiskCategory.CRITICAL.value]
    )
    high = len(
        [p for p in predictions if p.risk_category.value == RiskCategory.HIGH.value]
    )
    medium = len(
        [p for p in predictions if p.risk_category.value == RiskCategory.MEDIUM.value]
    )
    low = len(
        [p for p in predictions if p.risk_category.value == RiskCategory.LOW.value]
    )

    # Calculate mean score and std dev
    mean_score = (
        sum(p.normalized_score for p in predictions) / total_files
        if total_files > 0
        else 0
    )
    variance = (
        sum((p.normalized_score - mean_score) ** 2 for p in predictions) / total_files
        if total_files > 0
        else 0
    )
    std_dev = variance**0.5

    # Sort predictions by risk score (highest first)
    sorted_preds = sorted(predictions, key=lambda p: p.normalized_score, reverse=True)

    # Create lookup for database IDs if available
    db_id_lookup = {}
    if predictions_with_db_ids:
        for db_pred in predictions_with_db_ids:
            db_id_lookup[db_pred.get("file_path")] = db_pred.get("id")

    # Convert predictions to JSON for JavaScript with database IDs
    predictions_data = []
    for i, pred in enumerate(sorted_preds):
        # Use database ID if available, otherwise fallback to temp ID
        pred_id = db_id_lookup.get(pred.module, f"pred_{i}")

        predictions_data.append(
            {
                "id": pred_id,
                "file_path": pred.module,
                "risk_category": pred.risk_category.value,
                "risk_display": pred.risk_category.display_name,
                "normalized_score": round(pred.normalized_score, 2),
                "raw_prediction": round(pred.raw_prediction, 4),
            }
        )

    predictions_json = json.dumps(predictions_data)

    # Build file tree structure
    def build_file_tree():
        tree = {}
        for pred in predictions:
            parts = pred.module.split("/")
            current = tree
            for i, part in enumerate(parts):
                if part not in current:
                    if i == len(parts) - 1:  # It's a file
                        current[part] = pred
                    else:  # It's a folder
                        current[part] = {}
                current = current[part] if isinstance(current[part], dict) else current
        return tree

    def calculate_folder_stats(folder_dict):
        """Calculate average score and file count for a folder"""
        total_score = 0
        file_count = 0

        def traverse(d):
            nonlocal total_score, file_count
            for key, value in d.items():
                if hasattr(
                    value, "normalized_score"
                ):  # It's a prediction object (file)
                    total_score += value.normalized_score
                    file_count += 1
                elif isinstance(value, dict):  # It's a folder
                    traverse(value)

        traverse(folder_dict)
        avg_score = total_score / file_count if file_count > 0 else 0

        # Determine category based on 0-10 scale
        if avg_score >= 9:
            category = "critical"
        elif avg_score >= 7:
            category = "high"
        elif avg_score >= 5:
            category = "medium"
        else:
            category = "low"

        return avg_score, file_count, category

    def generate_tree_html(tree_dict, depth=0):
        """Generate HTML for file tree"""
        html = ""
        for name, content in sorted(tree_dict.items()):
            indent_style = f"style='margin-left: {depth * 20}px;'"

            if hasattr(content, "normalized_score"):  # It's a file
                category_class = content.risk_category.value
                html += f"""
                <div class="tree-file {category_class}" {indent_style}>
                    <div class="file-name">📄 {name}</div>
                    <div class="file-score">{content.normalized_score:.1f}</div>
                    <div class="risk-badge {category_class}">{content.risk_category.display_name}</div>
                </div>"""
            elif isinstance(content, dict):  # It's a folder
                avg_score, file_count, category = calculate_folder_stats(content)
                html += f"""
                <div class="tree-node" data-depth="{depth}">
                    <div class="tree-folder {category}" onclick="toggleFolder(this)" {indent_style}>
                        <span class="folder-toggle">▶</span>
                        <span class="folder-icon">📁</span>
                        <span class="folder-name">{name}</span>
                        <span class="folder-stats">
                            <span class="folder-count">{file_count} files</span>
                            <span class="folder-score">{avg_score:.3f}</span>
                            <span class="risk-badge {category}">{category.title()}</span>
                        </span>
                    </div>
                    <div class="collapsible">
                        {generate_tree_html(content, depth + 1)}
                    </div>
                </div>"""
        return html

    file_tree = build_file_tree()
    datetime.now().isoformat()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MaintSight - Maintenance Risk Analysis - {repo_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f8f9fa;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: white;
            padding: 40px 30px;
            border-radius: 15px;
            box-shadow: 0 4px 20px rgba(22, 104, 220, 0.1);
            margin-bottom: 30px;
            text-align: center;
            border: 1px solid rgba(22, 104, 220, 0.1);
        }}
        .header h1 {{
            color: #1668dc;
            margin-bottom: 8px;
            font-size: 2.2em;
            font-weight: 700;
            letter-spacing: -0.02em;
        }}
        .header p {{
            color: #3c89e8;
            font-size: 1.1em;
            margin-bottom: 20px;
            font-weight: 500;
            opacity: 0.8;
        }}
        .header .meta {{
            color: #3c89e8;
            font-size: 0.9em;
            opacity: 0.7;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(22, 104, 220, 0.1);
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            grid-template-rows: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
            max-width: 1000px;
            margin-left: auto;
            margin-right: auto;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .stat-label {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .stat-percentage {{
            font-size: 0.8em;
            margin-top: 5px;
        }}
        .low {{ color: #4CAF50; }}
        .medium {{ color: #1668dc; }}
        .high {{ color: #FF9500; }}
        .critical {{ color: #FF5757; }}
        .section {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        .section h2 {{
            color: #1668dc;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
        }}
        .section h2.overview::before {{ content: '📊'; margin-right: 10px; }}
        .section h2.top-files::before {{ content: '⚠️'; margin-right: 10px; }}
        .section h2.file-tree::before {{ content: '🌳'; margin-right: 10px; }}
        .tree-node {{
            margin-bottom: 10px;
        }}
        .tree-folder {{
            display: flex;
            align-items: center;
            padding: 8px 12px;
            margin: 2px 0;
            border-radius: 6px;
            background: #e6f4ff;
            border-left: 4px solid #1668dc;
            cursor: pointer;
            user-select: none;
            transition: all 0.2s ease;
            font-weight: 500;
        }}
        .tree-folder:hover {{
            background: #f0f5ff;
            border-left-color: #1554ad;
        }}
        .tree-folder.low {{
            border-left-color: #4CAF50;
            background: #E8F5E8;
        }}
        .tree-folder.medium {{
            border-left-color: #1668dc;
            background: #f0f5ff;
        }}
        .tree-folder.high {{
            border-left-color: #FF9500;
            background: #FFF5E6;
        }}
        .tree-folder.critical {{
            border-left-color: #FF5757;
            background: #FFE8E8;
        }}
        .tree-file {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            margin: 5px 0;
            border-radius: 6px;
            background: #f8f9fa;
            border-left: 4px solid #ddd;
        }}
        .tree-file.low {{
            border-left-color: #4CAF50;
            background: #E8F5E8;
        }}
        .tree-file.medium {{
            border-left-color: #1668dc;
            background: #f0f5ff;
        }}
        .tree-file.high {{
            border-left-color: #FF9500;
            background: #FFF5E6;
        }}
        .tree-file.critical {{
            border-left-color: #FF5757;
            background: #FFE8E8;
        }}
        .file-name {{
            flex: 1;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.9em;
        }}
        .file-score {{
            font-weight: bold;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.85em;
        }}
        .folder-toggle {{
            margin-right: 8px;
            font-size: 12px;
            transition: transform 0.2s ease;
            color: #1668dc;
        }}
        .folder-toggle.expanded {{
            transform: rotate(90deg);
        }}
        .folder-icon {{
            margin-right: 8px;
            font-size: 14px;
        }}
        .folder-name {{
            flex: 1;
            font-size: 0.9em;
            color: #2D3748;
        }}
        .folder-stats {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.8em;
        }}
        .folder-count {{
            color: #1668dc;
            background: #f0f5ff;
            padding: 2px 6px;
            border-radius: 10px;
            font-weight: 500;
        }}
        .folder-score {{
            font-family: 'Monaco', 'Menlo', monospace;
            font-weight: bold;
            color: #2D3748;
        }}
        .risk-badge {{
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-left: 10px;
        }}
        .risk-badge.low {{
            background: #4CAF50;
            color: white;
        }}
        .risk-badge.medium {{
            background: #1668dc;
            color: white;
        }}
        .risk-badge.high {{
            background: #FF9500;
            color: white;
        }}
        .risk-badge.critical {{
            background: #FF5757;
            color: white;
        }}
        .file-tree-container {{
            max-height: 600px;
            overflow-y: auto;
            padding: 10px;
            background: #f0f5ff;
            border-radius: 8px;
            border: 1px solid #65a9f3;
        }}
        .collapsible {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}
        .collapsible.expanded {{
            max-height: 2000px;
        }}
        .top-files-list {{
            max-height: 400px;
            overflow-y: auto;
        }}
        .top-file-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            margin: 5px 0;
            border-radius: 6px;
            background: #f8f9fa;
            border-left: 4px solid #ddd;
        }}
        .top-file-item.critical {{
            border-left-color: #FF5757;
            background: #FFE8E8;
        }}
        .top-file-item.high {{
            border-left-color: #FF9500;
            background: #FFF5E6;
        }}
        .top-file-item.medium {{
            border-left-color: #1668dc;
            background: #f0f5ff;
        }}
        .top-file-item.low {{
            border-left-color: #4CAF50;
            background: #E8F5E8;
        }}
        .footer {{
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
            margin-top: 30px;
            padding: 20px;
        }}
        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }}
        .stat-list {{
            list-style: none;
            padding: 0;
        }}
        .stat-list li {{
            padding: 8px 0;
            border-bottom: 1px solid #ecf0f1;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .stat-list li:last-child {{
            border-bottom: none;
        }}
        .file-type {{
            font-family: 'Monaco', 'Menlo', monospace;
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .risk-score {{
            font-family: 'Monaco', 'Menlo', monospace;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.85em;
        }}
        .risk-high {{ background: #fdedec; color: #e74c3c; }}
        .risk-medium {{ background: #fef9e7; color: #f39c12; }}
        .risk-low {{ background: #ebf3fd; color: #3498db; }}
        .risk-good {{ background: #eafaf1; color: #27ae60; }}
        .authors-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
            max-height: 280px;
            overflow-y: auto;
            padding: 10px;
            border: 1px solid #65a9f3;
            border-radius: 8px;
            background: #f0f5ff;
        }}
        .author-item {{
            display: flex;
            align-items: center;
            padding: 10px 15px;
            background: #e6f4ff;
            border-radius: 8px;
            border: 1px solid #65a9f3;
            border-left: 4px solid #1668dc;
            transition: background 0.2s ease;
        }}
        .author-item:hover {{
            background: #e9ecef;
        }}
        .author-avatar {{
            width: 35px;
            height: 35px;
            border-radius: 50%;
            background: #1668dc;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 14px;
            margin-right: 12px;
            flex-shrink: 0;
        }}
        .author-name {{
            font-size: 0.9em;
            color: #2c3e50;
            font-weight: 500;
            word-break: break-word;
        }}

        /* Interactive elements */
        .file-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            margin: 8px 0;
            border-radius: 8px;
            background: #f8f9fa;
            border-left: 4px solid #ddd;
            transition: all 0.3s ease;
        }}
        .file-item:hover {{
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transform: translateY(-1px);
        }}
        .file-item.low {{
            border-left-color: #4CAF50;
            background: #E8F5E8;
        }}
        .file-item.medium {{
            border-left-color: #1668dc;
            background: #f0f5ff;
        }}
        .file-item.high {{
            border-left-color: #FF9500;
            background: #FFF5E6;
        }}
        .file-item.critical {{
            border-left-color: #FF5757;
            background: #FFE8E8;
        }}

        .file-info {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
        }}
        .file-path {{
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.9em;
            font-weight: 600;
            color: #2D3748;
            margin-bottom: 4px;
        }}
        .file-score {{
            font-size: 0.8em;
            color: #666;
        }}

        .file-controls {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}

        .category-selector {{
            padding: 6px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            background: white;
            font-size: 0.85em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .category-selector:hover {{
            border-color: #1668dc;
        }}
        .category-selector.changed {{
            border-color: #FF9500;
            background: #FFF5E6;
        }}

        .search-box {{
            margin-bottom: 20px;
        }}
        .search-box input {{
            width: 100%;
            padding: 15px;
            font-size: 16px;
            border: 2px solid #dee2e6;
            border-radius: 8px;
            transition: border-color 0.3s;
        }}
        .search-box input:focus {{
            outline: none;
            border-color: #1668dc;
        }}

        .notification {{
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            z-index: 1000;
            transform: translateX(400px);
            transition: transform 0.3s ease;
        }}
        .notification.success {{
            background: #4CAF50;
        }}
        .notification.error {{
            background: #FF5757;
        }}
        .notification.show {{
            transform: translateX(0);
        }}

        .db-status {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 10px 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            font-size: 0.8em;
            border-left: 4px solid #4CAF50;
        }}
        .db-status.offline {{
            border-left-color: #FF5757;
        }}

        @media (max-width: 768px) {{
            .container {{ padding: 10px; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .header {{ padding: 30px 20px; }}
            .header h1 {{ font-size: 1.8em; }}
            .two-column {{ grid-template-columns: 1fr; }}
            .authors-grid {{ grid-template-columns: 1fr; max-height: 400px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 MaintSight - Interactive Risk Analysis</h1>
            <p>Click risk categories to edit • Changes are automatically saved</p>
            <div class="meta">
                <strong>Repository:</strong> {repo_name}<br>
                <strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}<br>
                <strong>API Server:</strong> {api_base_url}<br>
                {f"<strong>Run ID:</strong> {run_id}<br>" if run_id else ""}
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number low">{low}</div>
                <div class="stat-label">Low Risk</div>
                <div class="stat-percentage low">{(low / total_files * 100):.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-number medium">{medium}</div>
                <div class="stat-label">Medium Risk</div>
                <div class="stat-percentage medium">{(medium / total_files * 100):.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-number high">{high}</div>
                <div class="stat-label">High Risk</div>
                <div class="stat-percentage high">{(high / total_files * 100):.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-number critical">{critical}</div>
                <div class="stat-label">Critical Risk</div>
                <div class="stat-percentage critical">{(critical / total_files * 100):.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_files}</div>
                <div class="stat-label">Total Files</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{mean_score:.4f}</div>
                <div class="stat-label">Mean Risk Score</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{std_dev:.4f}</div>
                <div class="stat-label">Standard Deviation</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len([p for p in predictions if p.normalized_score >= 7])}</div>
                <div class="stat-label">Files Needing Attention</div>
            </div>
        </div>

        <div class="section">
            <h2 class="overview">Analysis Overview</h2>
            <p><strong>Repository Analysis:</strong> This comprehensive report analyzes {total_files} files in the {repo_name} repository to assess maintenance risk and code quality trends.</p>
            <br>
            <p><strong>Risk Categories:</strong></p>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li><strong class="low">Low Risk (0-4.9):</strong> Code quality is good - minimal maintenance needed</li>
                <li><strong class="medium">Medium Risk (5.0-6.9):</strong> Some attention needed - consider monitoring</li>
                <li><strong class="high">High Risk (7.0-8.9):</strong> Moderate degradation - consider refactoring</li>
                <li><strong class="critical">Critical Risk (9.0-10.0):</strong> Critical attention needed - immediate action required</li>
            </ul>
        </div>

        <div class="section">
            <h2>📝 Interactive File Risk Analysis</h2>
            <p>Click on any risk category dropdown to change the classification. Changes are automatically saved to the central database.</p>

            <div class="search-box">
                <input type="text" id="searchInput" placeholder="🔍 Search files..." onkeyup="filterFiles()">
            </div>

            <div id="filesList">
                <!-- Files will be populated by JavaScript -->
            </div>
        </div>

        <div class="section">
            <h2 class="file-tree">Complete File Analysis Tree</h2>
            <div class="file-tree-container">
                {generate_tree_html(file_tree)}
            </div>
        </div>

        {_generate_commit_stats_sections(predictions, commit_data)}

        <div class="footer">
            <p>Generated by <strong>MaintSight</strong> • Interactive HTML Report with Database Integration</p>
            <p>Risk scores based on commit patterns, code churn, and development activity analysis</p>
        </div>
    </div>

    <!-- Notification element -->
    <div id="notification" class="notification"></div>

     <!-- Database status indicator -->
    <div id="dbStatus" class="db-status">
        <span id="dbStatusText">Checking database connection...</span>
    </div>

    <script>
        // Configuration
        const API_BASE_URL = '{api_base_url}';
        const REPOSITORY_PATH = '{repository_path}';
        const RUN_ID = '{run_id or ""}';

        // Predictions data
        const predictions = {predictions_json};

        // State
        let dbConnected = false;

        // Initialize the page
        document.addEventListener('DOMContentLoaded', function() {{
            checkDatabaseConnection().then(() => {{
                // After checking DB connection, refresh data if possible
                if (dbConnected) {{
                    refreshPredictionsFromDatabase();
                }} else {{
                    renderFiles();
                }}
            }});
        }});

        // Check database connection
        async function checkDatabaseConnection() {{
            try {{
                const response = await fetch(`${{API_BASE_URL}}/health`);
                dbConnected = response.ok;
                updateDbStatus(dbConnected);
                return dbConnected;
            }} catch (error) {{
                dbConnected = false;
                updateDbStatus(false);
                return false;
            }}
        }}

        // Update database status indicator
        function updateDbStatus(connected) {{
            const statusEl = document.getElementById('dbStatus');
            const textEl = document.getElementById('dbStatusText');

            if (connected) {{
                statusEl.className = 'db-status';
                textEl.textContent = '✅ Database connected';
            }} else {{
                statusEl.className = 'db-status offline';
                textEl.textContent = '❌ Database offline - changes will not be saved';
            }}
        }}

        // Refresh predictions from database if available
        async function refreshPredictionsFromDatabase() {{
            if (!dbConnected) {{
                renderFiles();
                return;
            }}

            // If we have a RUN_ID, try to get the latest prediction data for this run
            if (RUN_ID && RUN_ID.length > 0) {{
                await fetchLatestRunData();
            }}

            renderFiles();
        }}

        // Fetch latest data for the current run
        async function fetchLatestRunData() {{
            try {{
                const response = await fetch(`${{API_BASE_URL}}/api/v1/cli/runs/${{RUN_ID}}/predictions`, {{
                    method: 'GET',
                    headers: {{ 'Content-Type': 'application/json' }}
                }});

                if (response.ok) {{
                    const apiResponse = await response.json();
                    const dbPredictions = apiResponse.predictions || [];

                    // Update predictions with database data
                    dbPredictions.forEach(dbPred => {{
                        // Find matching prediction by file path
                        const index = predictions.findIndex(p => p.file_path === dbPred.file_path);
                        if (index !== -1) {{
                            // Update the ID to match database
                            if (dbPred.id) {{
                                predictions[index].id = dbPred.id;
                            }}

                            // Use updated_risk_category if available (user has modified it),
                            // otherwise use original risk_category
                            const currentCategory = dbPred.updated_risk_category || dbPred.risk_category;

                            if (currentCategory && predictions[index].risk_category !== currentCategory) {{
                                predictions[index].risk_category = currentCategory;
                            }}
                        }}
                    }});
                }}
            }} catch (error) {{
                // Silent fail - continue with static data
            }}
        }}




        // Render files list
        function renderFiles() {{
            const container = document.getElementById('filesList');
            container.innerHTML = '';

            predictions.forEach((pred, index) => {{
                const fileItem = createFileItem(pred, index);
                container.appendChild(fileItem);
            }});
        }}

        // Create file item element
        function createFileItem(pred, index) {{
            const item = document.createElement('div');
            item.className = `file-item ${{pred.risk_category}}`;
            item.id = `file-${{index}}`;

            item.innerHTML = `
                <div class="file-info">
                    <div class="file-path">${{pred.file_path}}</div>
                    <div class="file-score">Raw: ${{pred.raw_prediction}} | Normalized: ${{pred.normalized_score}}</div>
                </div>
                <div class="file-controls">
                    <div class="risk-score ${{pred.risk_category}}">${{pred.normalized_score}}</div>
                    <select class="category-selector" onchange="updateCategory('${{pred.id}}', this.value, ${{index}})">
                        <option value="low" ${{pred.risk_category === 'low' ? 'selected' : ''}}>Low</option>
                        <option value="medium" ${{pred.risk_category === 'medium' ? 'selected' : ''}}>Medium</option>
                        <option value="high" ${{pred.risk_category === 'high' ? 'selected' : ''}}>High</option>
                        <option value="critical" ${{pred.risk_category === 'critical' ? 'selected' : ''}}>Critical</option>
                    </select>
                </div>
            `;

            return item;
        }}

        // Update category and save to database
        async function updateCategory(predId, newCategory, index) {{
            const pred = predictions[index];
            if (!pred) {{
                return;
            }}

            const oldCategory = pred.risk_category;

            if (oldCategory === newCategory) {{
                return; // No change
            }}

            // Update UI immediately (optimistic update)
            pred.risk_category = newCategory;
            updateFileItemVisuals(index, newCategory);

            // Save to database if connected
            if (dbConnected) {{
                try {{
                    const requestBody = {{
                        prediction_id: predId,
                        new_category: newCategory,
                        notes: `Changed from ${{oldCategory}} to ${{newCategory}} via HTML interface`,
                        user_identifier: 'html_interface'
                    }};

                    const response = await fetch(`${{API_BASE_URL}}/api/v1/predictions/${{predId}}/category`, {{
                        method: 'PUT',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify(requestBody)
                    }});

                    if (response.ok) {{
                        // Database update was successful - refresh data from database to get the latest state
                        if (RUN_ID && RUN_ID.length > 0) {{
                            await fetchLatestRunData();
                            // Re-render with updated data
                            renderFiles();
                        }} else {{
                            // Fallback: trust the optimistic update
                            pred.risk_category = newCategory;
                            updateFileItemVisuals(index, newCategory);
                        }}

                        showNotification(`✅ Updated ${{pred.file_path}} to ${{newCategory}}`, 'success');
                    }} else {{
                        showNotification(`❌ Failed to save changes for ${{pred.file_path}}`, 'error');
                        // Revert UI change
                        pred.risk_category = oldCategory;
                        updateFileItemVisuals(index, oldCategory);
                    }}
                }} catch (error) {{
                    showNotification(`❌ Network error updating ${{pred.file_path}}`, 'error');
                    // Revert UI change
                    pred.risk_category = oldCategory;
                    updateFileItemVisuals(index, oldCategory);
                }}
            }} else {{
                showNotification(`⚠️ Database offline - change to ${{pred.file_path}} not saved`, 'error');
            }}
        }}


        // Update file item visual appearance
        function updateFileItemVisuals(index, newCategory) {{
            const fileItem = document.getElementById(`file-${{index}}`);
            if (!fileItem) {{
                return;
            }}

            const selector = fileItem.querySelector('.category-selector');
            const riskScore = fileItem.querySelector('.risk-score');

            // Update all classes that depend on category
            fileItem.className = `file-item ${{newCategory}}`;
            if (riskScore) {{
                // Remove old category classes and add new one
                riskScore.className = `risk-score ${{newCategory}}`;
            }}

            // Mark selector as changed
            if (selector) {{
                selector.classList.add('changed');
                selector.value = newCategory;
            }}

            // Force DOM update
            fileItem.offsetHeight; // Trigger reflow
        }}

        // Show notification
        function showNotification(message, type) {{
            const notification = document.getElementById('notification');
            notification.textContent = message;
            notification.className = `notification ${{type}} show`;

            setTimeout(() => {{
                notification.classList.remove('show');
            }}, 3000);
        }}

        // Filter files based on search
        function filterFiles() {{
            const input = document.getElementById('searchInput');
            const filter = input.value.toLowerCase();
            const fileItems = document.querySelectorAll('.file-item');

            fileItems.forEach(item => {{
                const filePath = item.querySelector('.file-path').textContent.toLowerCase();
                if (filePath.indexOf(filter) > -1) {{
                    item.style.display = '';
                }} else {{
                    item.style.display = 'none';
                }}
            }});
        }}

        // File tree functionality (preserved)
        function toggleFolder(element) {{
            const content = element.nextElementSibling;
            const toggle = element.querySelector('.folder-toggle');
            if (content && content.classList.contains('collapsible')) {{
                content.classList.toggle('expanded');
                toggle.classList.toggle('expanded');
            }}
        }}

        document.addEventListener('keydown', function(e) {{
            if (e.target.classList.contains('tree-folder')) {{
                if (e.key === 'Enter' || e.key === ' ') {{
                    e.preventDefault();
                    toggleFolder(e.target);
                }}
            }}
        }});

        // Periodic database connection check
        setInterval(checkDatabaseConnection, 30000); // Check every 30 seconds
    </script>
</body>
</html>"""


def _show_summary(predictions, logger):
    """Show summary statistics."""
    dist = {}
    for pred in predictions:
        category = pred.risk_category.value
        dist[category] = dist.get(category, 0) + 1

    logger.info("Summary:", "📊")
    print(f"Total files: {len(predictions)}")
    print(f"Critical: {dist.get('critical', 0)}")
    print(f"High: {dist.get('high', 0)}")
    print(f"Medium: {dist.get('medium', 0)}")
    print(f"Low: {dist.get('low', 0)}")


if __name__ == "__main__":
    main()
