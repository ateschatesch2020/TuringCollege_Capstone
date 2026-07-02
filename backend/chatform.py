import os

from tools import search_files_with_progress, _file_size_str, _build_file_select_block


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
                found = payload["exact"]
                if found:
                    section = [f"Exact matches for '{keyword}' ({len(found)}):"]
                    for f in found:
                        section.append(f"  {f} ({_file_size_str(f)})")
                    if len(found) >= 20:
                        section.append("  ... (truncated at 20 results)")
                    results.append("\n".join(section) + _build_file_select_block(found))
                else:
                    results.append(f"No file named '{keyword}' found under {projects_dir}.")
            if contains:
                found = payload["contains"]
                if found:
                    section = [f"Files with '{keyword}' in name ({len(found)}):"]
                    for f in found:
                        section.append(f"  {f} ({_file_size_str(f)})")
                    if len(found) >= 30:
                        section.append("  ... (truncated at 30 results)")
                    results.append("\n".join(section) + _build_file_select_block(found))
                else:
                    results.append(f"No files with '{keyword}' in their name found under {projects_dir}.")

            yield ("done", "\n\n".join(results) if results else "No files found.")
