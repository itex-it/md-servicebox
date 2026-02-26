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
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get/create Paperless tag '{tag_name}' (Network error): {e}")
            return "OFFLINE"
        except Exception as e:
            logger.error(f"Failed to get/create Paperless tag '{tag_name}': {e}")
            return None

    def upload_document(self, file_path: str, title: str, tags: list = None):
        """
        Uploads a PDF to Paperless-ngx.
        Returns the new Paperless Document ID or 'PROCESSING_IN_PAPERLESS' on success,
        'OFFLINE' if Paperless is unreachable, or None on failure.
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
                    if t_id == "OFFLINE":
                        return "OFFLINE"
                    if t_id:
                        tag_ids.append(t_id)
                        
            # Prepare payload
            data = {"title": title}
            if tag_ids:
                data["tags"] = tag_ids
                
            # Upload file
            with open(file_path, "rb") as f:
                files = {"document": (os.path.basename(file_path), f, "application/pdf")}
                
                res = requests.post(f"{self.url}/api/documents/post_document/", headers=self.headers, data=data, files=files, timeout=30)
                
            res.raise_for_status()
            
            response_data = res.text
            logger.info(f"Successfully pushed to Paperless. Response: {response_data}")
            
            import time
            time.sleep(2)
            
            search_res = requests.get(f"{self.url}/api/documents/", headers=self.headers, params={"title__iexact": title}, timeout=10)
            
            if search_res.ok and search_res.json().get("count", 0) > 0:
                 doc_id = search_res.json()["results"][0]["id"]
                 return doc_id
            
            return "PROCESSING_IN_PAPERLESS"
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Paperless is unreachable (Network/Timeout): {e}")
            return "OFFLINE"
        except Exception as e:
            logger.error(f"Paperless Upload Error: {e}")
            return None

paperless_client = PaperlessClient()
