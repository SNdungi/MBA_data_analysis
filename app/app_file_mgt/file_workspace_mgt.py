import os
import shutil
from flask import current_app

class WorkspaceManager:
    @staticmethod
    def get_base_path(study_id):
        """Returns the temp path for a specific study session."""
        # Store in instance/temp, NOT static (for security)
        base = os.path.join(current_app.instance_path, 'temp_workspaces', str(study_id))
        os.makedirs(base, exist_ok=True)
        return base

    @staticmethod
    def save_temp_file(study_id, filename, file_storage_or_text):
        """Saves a file from the browser to the temp workspace."""
        path = os.path.join(WorkspaceManager.get_base_path(study_id), filename)
        
        if hasattr(file_storage_or_text, 'save'):
            # It's a Flask FileStorage object
            file_storage_or_text.save(path)
        else:
            # It's a string/text
            with open(path, 'w', encoding='utf-8') as f:
                f.write(file_storage_or_text)
        return path

    @staticmethod
    def get_temp_file_path(study_id, filename):
        """Gets path for Pandas to read."""
        return os.path.join(WorkspaceManager.get_base_path(study_id), filename)

    @staticmethod
    def read_temp_file(study_id, filename):
        """Reads file content to send back to browser."""
        path = os.path.join(WorkspaceManager.get_base_path(study_id), filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    @staticmethod
    def clear_workspace(study_id):
        """Deletes the temp folder when user leaves."""
        path = WorkspaceManager.get_base_path(study_id)
        if os.path.exists(path):
            shutil.rmtree(path)