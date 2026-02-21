import requests
from config_loader import config, logger
import os

class PaperlessClient:
    def __init__(self):
        raw_url = config.get("paperless_url", "").rstrip("/")
        if raw_url.endswith("/api"):
            raw_url = raw_url[:-4]
        self.url = raw_url
        self.token = config.get("paperless_token", "")
        self.enabled = config.get("paperless_enabled", False)
        
        self.headers = {
            "Authorization": f"Token {self.token}"
        }

    def _get_or_create_tag(self, tag_name: str) -> int:
        """Finds a tag by name, creates it if it doesn't exist. Returns the Tag ID."""
        if not self.enabled or not self.url or not self.token:
            return None
            
        try:
            # Search for tag
            res = requests.get(f"{self.url}/api/tags/", headers=self.headers, params={"name__iexact": tag_name})
            res.raise_for_status()
            data = res.json()
            
            if data.get("count", 0) > 0:
                return data["results"][0]["id"]
                
            # Create tag if it doesn't exist
            res_create = requests.post(
                f"{self.url}/api/tags/", 
                headers=self.headers,
                json={"name": tag_name}
            )
            res_create.raise_for_status()
            return res_create.json()["id"]
            
        except Exception as e:
            logger.error(f"Failed to get/create Paperless tag '{tag_name}': {e}")
            return None

    def upload_document(self, file_path: str, title: str, tags: list = None) -> int:
        """
        Uploads a PDF to Paperless-ngx.
        Returns the new Paperless Document ID on success, or None on failure.
        """
        if not self.enabled or not self.url or not self.token:
            logger.info("Paperless integration is disabled or not fully configured.")
            return None
            
        if not os.path.exists(file_path):
            logger.error(f"Cannot upload to Paperless: File not found {file_path}")
            return None
            
        try:
            # Resolve tag IDs
            tag_ids = []
            if tags:
                for tag_name in tags:
                    t_id = self._get_or_create_tag(tag_name)
                    if t_id:
                        tag_ids.append(t_id)
                        
            # Prepare payload
            data = {"title": title}
            if tag_ids:
                data["tags"] = tag_ids
                
            # Upload file
            with open(file_path, "rb") as f:
                files = {"document": (os.path.basename(file_path), f, "application/pdf")}
                
                # Note: Content-Type header should NOT be set manually when using the `files` parameter, 
                # requests handles the multipart boundary automatically.
                res = requests.post(f"{self.url}/api/documents/post_document/", headers=self.headers, data=data, files=files)
                
            res.raise_for_status()
            
            # The post_document API often returns a task ID rather than the document ID directly if async.
            # Usually it looks like: "OK" or a task identifier. Paperless processes it in the background.
            # Due to this async nature, getting the immediate document ID can be tricky.
            # Let's inspect the response to see if an ID is returned directly. 
            response_data = res.text
            logger.info(f"Successfully pushed to Paperless. Response: {response_data}")
            
            # Since post_document is asynchronous, we need to poll for the document ID using the file name or return the task ID.
            # For simplicity, if we don't get the ID instantly, we will have to search for the document by title.
            # Or use a fallback. We will return a placeholder for now and implement searching.
            
            # Wait a moment for paperless to injest it before searching
            import time
            time.sleep(2)
            
            search_res = requests.get(f"{self.url}/api/documents/", headers=self.headers, params={"title__iexact": title})
            
            if search_res.ok and search_res.json().get("count", 0) > 0:
                 doc_id = search_res.json()["results"][0]["id"]
                 return doc_id
            
            # Fallback if not immediately searchable (e.g. background queue)
            # We return a negative "Task" ID flag or a string to indicate it's processing
            return "PROCESSING_IN_PAPERLESS"
            
        except Exception as e:
            logger.error(f"Paperless Upload Error: {e}")
            return None

paperless_client = PaperlessClient()
