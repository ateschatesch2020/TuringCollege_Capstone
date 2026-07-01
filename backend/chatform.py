from tools import find_files_by_name_exact, find_files_by_name_contains


class FormManager:
    def search(self, keyword: str, exact: bool, contains: bool) -> str:
        results = []
        if exact:
            results.append(find_files_by_name_exact.invoke({"filename": keyword}))
        if contains:
            results.append(find_files_by_name_contains.invoke({"keyword": keyword}))
        return "\n\n".join(results) if results else "No files found."
