import os
import re
from pathlib import Path

# --- CONFIGURATION ---
from core.tools.infrastructure.config import settings
PROJECT_ROOT = settings.PROJECT_ROOT
TOOLS_DIR = PROJECT_ROOT / "core" / "tools"

class SmartJanitor:
    def __init__(self, target_directory_path_to_clean_and_scan: Path):
        self.target_directory_path_to_clean_and_scan = target_directory_path_to_clean_and_scan
        self.detected_unused_ghost_definitions_list = []

    def find_all_python_files(self):
        """Returns a list of all .py files in the target directory."""
        accumulated_python_source_file_paths_list = []
        for current_directory_walk_root_path, skipped_subdirectories_list, current_directory_files_list in os.walk(self.target_directory_path_to_clean_and_scan):
            if "__pycache__" in current_directory_walk_root_path:
                continue
            for current_evaluated_file_name in current_directory_files_list:
                if current_evaluated_file_name.endswith(".py"):
                    accumulated_python_source_file_paths_list.append(Path(current_directory_walk_root_path) / current_evaluated_file_name)
        return accumulated_python_source_file_paths_list

    def extract_definitions(self, raw_python_file_text_content: str):
        """Extracts function and class names from file content."""
        # Matches 'def function_name(' or 'class ClassName:'
        extracted_regex_matches_for_classes_and_functions = re.findall(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\(', raw_python_file_text_content)
        extracted_regex_matches_for_classes_and_functions += re.findall(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)[:\(]', raw_python_file_text_content)
        return set(extracted_regex_matches_for_classes_and_functions)

    def is_used_anywhere_else(self, target_definition_name_to_check: str, source_file_path_where_definition_resides: Path, pre_loaded_files_contents_dictionary: dict):
        """Checks if a name is referenced in any other file's content."""
        for evaluated_file_path_key, evaluated_file_text_content in pre_loaded_files_contents_dictionary.items():
            if evaluated_file_path_key == source_file_path_where_definition_resides:
                continue
            if target_definition_name_to_check in evaluated_file_text_content:
                return True
        return False

    def hunt_ghosts(self):
        print(f"🧹 Smart Janitor is entering the 'Ghost Hunt' phase...")
        all_discovered_python_files_list = self.find_all_python_files()
        print(f"  - Scanning {len(all_discovered_python_files_list)} files into memory...")

        # O(M) Pre-load all files into memory safely
        pre_loaded_files_contents_dictionary = {}
        for current_source_file_to_load_or_check in all_discovered_python_files_list:
            try:
                with open(current_source_file_to_load_or_check, "r", encoding="utf-8", errors="ignore") as source_file_io_stream_handle:
                    pre_loaded_files_contents_dictionary[current_source_file_to_load_or_check] = source_file_io_stream_handle.read()
            except Exception as file_read_exception_instance:
                print(f"    ⚠️ Skipping {current_source_file_to_load_or_check.name}: {file_read_exception_instance}")

        # O(N) definitions searched against pre-loaded memory
        for current_source_file_to_load_or_check, python_file_raw_text_content in pre_loaded_files_contents_dictionary.items():
            discovered_class_and_function_definitions_set = self.extract_definitions(python_file_raw_text_content)
            for individual_definition_name in discovered_class_and_function_definitions_set:
                # Skip common or internal names
                if individual_definition_name.startswith("__") or individual_definition_name in ["main", "run", "setup"]:
                    continue
                
                if not self.is_used_anywhere_else(individual_definition_name, current_source_file_to_load_or_check, pre_loaded_files_contents_dictionary):
                    self.detected_unused_ghost_definitions_list.append({"name": individual_definition_name, "file": current_source_file_to_load_or_check})

        print(f"✅ Hunt complete. Found {len(self.detected_unused_ghost_definitions_list)} potential ghost functions/classes.")
        return self.detected_unused_ghost_definitions_list

    def report(self):
        if not self.detected_unused_ghost_definitions_list:
            print("✨ Your codebase is lean! No ghosts detected.")
            return

        print("\n👻 --- GHOST REPORT --- 👻")
        for detected_unused_ghost_record_dictionary in self.detected_unused_ghost_definitions_list:
            print(f"  - {detected_unused_ghost_record_dictionary['name']} (Defined in: {detected_unused_ghost_record_dictionary['file'].relative_to(PROJECT_ROOT)})")
        print("\n⚠️ WARNING: These functions are never called by other files.")

if __name__ == "__main__":
    janitor = SmartJanitor(TOOLS_DIR)
    janitor.hunt_ghosts()
    janitor.report()
