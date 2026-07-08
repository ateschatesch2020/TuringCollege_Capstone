import os

from tools import search_files_with_progress, _format_name_matches


class FormManager:
    def search_with_progress(self, keyword: str, exact: bool, contains: bool):
        """Generator: yields ("counting", None), then ("progress", pct), then a final ("done", result_text)."""
        projects_dir = os.getenv("PROJECTS_DIR")
        if not projects_dir:
            yield ("done", "PROJECTS_DIR environment variable is not set.")
            return

        for kind, payload in search_files_with_progress(
            projects_dir,
            filename=keyword if exact else None,
            keyword=keyword if contains else None,
        ):
            if kind == "counting":
                yield ("counting", None)
                continue
            if kind == "progress":
                yield ("progress", payload)
                continue

            results = []
            if exact:
                results.append(_format_name_matches(
                    payload["exact"], f"Exact matches for '{keyword}'", 20,
                    f"No file named '{keyword}' found under {projects_dir}.",
                ))
            if contains:
                results.append(_format_name_matches(
                    payload["contains"], f"Files with '{keyword}' in name", 30,
                    f"No files with '{keyword}' in their name found under {projects_dir}.",
                ))

            yield ("done", "\n\n".join(results) if results else "No files found.")
