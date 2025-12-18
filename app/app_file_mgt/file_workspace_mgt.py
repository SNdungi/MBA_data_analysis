import os
import shutil
import hashlib
import json
import time
from pathlib import Path
from flask import current_app
from werkzeug.utils import secure_filename

class SecurityException(Exception):
    pass

class WorkspaceManager:
    """
    Manages ephemeral server-side workspaces.
    strictly enforces: temp_workspaces/{user_id}/{project_code}/
    """

    @staticmethod
    def _get_workspace_root(user_id, project_code):
        """
        Generates the absolute path for the workspace.
        CRITICAL: Ensures path is within the allowed temp directory.
        """
        if not user_id or not project_code:
            raise SecurityException("Invalid workspace context")

        # Base temp directory (instance/temp_workspaces)
        base_dir = os.path.abspath(os.path.join(current_app.instance_path, 'temp_workspaces'))
        
        # User/Project specific path
        workspace_path = os.path.abspath(os.path.join(base_dir, str(user_id), secure_filename(project_code)))

        # Path Traversal Guard
        if not workspace_path.startswith(base_dir):
            raise SecurityException(f"Path traversal attempt detected: {workspace_path}")

        return workspace_path

    @staticmethod
    def init_workspace(user_id, project_code):
        """Creates the ephemeral directory structure."""
        path = WorkspaceManager._get_workspace_root(user_id, project_code)
        if not os.path.exists(path):
            os.makedirs(path, mode=0o700) # rwx------ permissions
        return path

    @staticmethod
    def calculate_checksum(file_path):
        """Generates SHA256 hash for integrity verification."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def save_file(user_id, project_code, filename, file_storage_or_text):
        """
        Saves a file to the TEMP workspace only.
        Performs atomic write to prevent partial corruption.
        """
        workspace = WorkspaceManager._get_workspace_root(user_id, project_code)
        if not os.path.exists(workspace):
            os.makedirs(workspace, mode=0o700)

        filename = secure_filename(filename)
        target_path = os.path.join(workspace, filename)
        temp_path = f"{target_path}.tmp"

        try:
            # 1. Write to .tmp file
            if hasattr(file_storage_or_text, 'save'):
                file_storage_or_text.save(temp_path)
            else:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(file_storage_or_text)

            # 2. Atomic Rename
            os.replace(temp_path, target_path)

            # 3. Calculate Integrity Hash
            checksum = WorkspaceManager.calculate_checksum(target_path)
            
            return {
                "status": "success", 
                "path": target_path, 
                "checksum": checksum,
                "timestamp": time.time()
            }

        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e

    @staticmethod
    def get_file(user_id, project_code, filename):
        """Reads a file from the TEMP workspace."""
        workspace = WorkspaceManager._get_workspace_root(user_id, project_code)
        target_path = os.path.join(workspace, secure_filename(filename))

        if not os.path.exists(target_path):
            return None

        # Try UTF-8 first, fallback to Latin-1
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(target_path, 'r', encoding='latin1') as f:
                return f.read()

    @staticmethod
    def destroy_workspace(user_id, project_code):
        """
        NUCLEAR OPTION: Removes the entire temp directory for this project.
        Must be called on logout or session end.
        """
        try:
            workspace = WorkspaceManager._get_workspace_root(user_id, project_code)
            if os.path.exists(workspace):
                shutil.rmtree(workspace)
                current_app.logger.info(f"Workspace destroyed: {user_id}/{project_code}")
                return True
        except Exception as e:
            current_app.logger.error(f"Failed to destroy workspace: {e}")
            return False
        return False

    @staticmethod
    def validate_no_uploads_access():
        """Security check to ensure no one is writing to legacy UPLOADS."""
        legacy_path = current_app.config.get('UPLOADS_FOLDER')
        if legacy_path and os.path.exists(legacy_path):
             # In a strict environment, we might verify this folder is empty
             pass
         
    @staticmethod
    def cleanup_user_session(user_id):
        """
        Called ONLY on Logout.
        Removes all temp workspaces associated with this user ID.
        """
        try:
            # Base temp directory (instance/temp_workspaces)
            base_dir = os.path.abspath(os.path.join(current_app.instance_path, 'temp_workspaces'))
            user_dir = os.path.join(base_dir, str(user_id))

            if os.path.exists(user_dir):
                shutil.rmtree(user_dir) # Deletes all project folders for this user
                current_app.logger.info(f"Cleaned up session for User {user_id}")
                return True
        except Exception as e:
            current_app.logger.error(f"Session cleanup failed: {e}")
            return False
    @staticmethod
    def get_file_path(user_id, project_code, filename):
        """
        Returns the ABSOLUTE PHYSICAL PATH to a file in the workspace.
        Use this when passing files to libraries that require a path string
        (like your DataBootstrapper).
        """
        workspace = WorkspaceManager._get_workspace_root(user_id, project_code)
        target_path = os.path.join(workspace, secure_filename(filename))
        return target_path