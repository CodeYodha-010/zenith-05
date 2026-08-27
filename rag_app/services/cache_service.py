import hashlib
import json
import os
import time
from pathlib import Path


class CacheService:
    def __init__(self, cache_dir="cache", ttl_seconds=3600):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = ttl_seconds
    
    def _get_cache_key(self, key):
        return hashlib.md5(str(key).encode()).hexdigest()
    
    def _get_cache_path(self, key):
        return self.cache_dir / f"{self._get_cache_key(key)}.json"
    
    def get(self, key):
        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
            
            if time.time() - data.get('timestamp', 0) > self.ttl:
                cache_path.unlink()
                return None
            
            return data.get('value')
        except:
            return None
    
    def set(self, key, value):
        cache_path = self._get_cache_path(key)
        data = {
            'timestamp': time.time(),
            'key': str(key),
            'value': value
        }
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
            return True
        except:
            return False
    
    def delete(self, key):
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
            return True
        return False
    
    def clear(self):
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
        return True
    
    def clear_expired(self):
        count = 0
        for f in self.cache_dir.glob("*.json"):
            try:
                with open(f, 'r') as fp:
                    data = json.load(fp)
                if time.time() - data.get('timestamp', 0) > self.ttl:
                    f.unlink()
                    count += 1
            except:
                f.unlink()
                count += 1
        return count
