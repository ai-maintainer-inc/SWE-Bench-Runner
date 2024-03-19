import pytest
from benchmarks.evaluate_line_diff import parse_diff


class TestParseDiff:
    # Test with a simple diff containing only additions
    def test_simple_diff_with_only_additions(self):
        diff = """
--- a/file.py
+++ b/file.py
@@ -1,2 +1,3 @@ + line 1
+ line 2
+ line 3
"""
        expected_changes = {
            "file.py": {
                "addition": [1, 2, 3],
                "deletion": [],
                "delete_windows": [(1, 3)],
            }
        }
        assert parse_diff(diff) == expected_changes

    # Test with a simple diff containing only deletions
    def test_simple_diff_with_only_deletions(self):
        diff = """
--- a/file.py
+++ b/file.py
@@ -1,3 +0,0 @@ - line 1
- line 2
- line 3
"""
        expected_changes = {
            "file.py": {
                "addition": [],
                "deletion": [1, 2, 3],
                "delete_windows": [(1, 4)],
            }
        }
        assert parse_diff(diff) == expected_changes

    # Test with a simple diff containing both additions and deletions
    def test_simple_diff_with_additions_and_deletions(self):
        diff = """
--- a/file.py
+++ b/file.py
@@ -1,2 +1,2 @@ - line 1
+ line 1
+ line 3
"""
        expected_changes = {
            "file.py": {
                "addition": [1, 2],
                "deletion": [1],
                "delete_windows": [(1, 3)],
            },
        }
        assert parse_diff(diff) == expected_changes

    # Test with an empty diff
    def test_empty_diff(self):
        diff = """
"""
        expected_changes = {}
        assert parse_diff(diff) == expected_changes

    # Test with a diff containing no changes
    def test_diff_with_no_changes(self):
        diff = """
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@ line 1
 line 2
 line 3
"""
        expected_changes = {}
        assert parse_diff(diff) == expected_changes

    # Test with a diff spanning multiple files
    def test_multi_file_diff(self):
        diff = """
--- a/file1.py
+++ b/file1.py
@@ -1,2 +1,3 @@ line 1
+ line 2 added in file1
line 2

--- /dev/null
+++ b/file2.txt
@@ -0,0 +1,2 @@ + line 1 added in file2
+ line 2 added in file2

--- a/file3.py
+++ b/file3.py
@@ -1,3 +1,2 @@ line 1
- line 2 deleted from file3
line 3
"""
        expected_changes = {
            "file1.py": {"addition": [2], "deletion": [], "delete_windows": [(1, 3)]},
            "file2.txt": {
                "addition": [1, 2],
                "deletion": [],
                "delete_windows": [(0, 0)],
            },
            "file3.py": {"addition": [], "deletion": [2], "delete_windows": [(1, 4)]},
        }
        assert parse_diff(diff) == expected_changes

    # Test with multiple chunks in multiple files
    def test_multi_chunk_diff(self):
        diff = """
--- a/fileA.py
+++ b/fileA.py
@@ -1,3 +1,4 @@ line 1
+ line 2 added in fileA chunk1
- line 2 deleted from fileA chunk1
 line 4
@@ -6,3 +6,4 @@ line 6
+ line 7 added in fileA chunk2
- line 7 deleted from fileA chunk2
 line 9

--- a/fileB.py
+++ b/fileB.py
@@ -1,2 +1,4 @@ line 1
- line 2 deleted from fileB chunk1
+ line 2 added in fileB chunk1
+ line 3 added in fileB chunk1
@@ -5,4 +5,4 @@ line 5
+ New line 6 added in fileB chunk2
- line 6 deleted from fileB chunk2
 line 8
"""
        expected_changes = {
            "fileA.py": {
                "addition": [2, 7],
                "deletion": [2, 7],
                "delete_windows": [(1, 4), (6, 9)],
            },
            "fileB.py": {
                "addition": [2, 3, 6],
                "deletion": [2, 6],
                "delete_windows": [(1, 3), (5, 9)],
            },
        }
        assert parse_diff(diff) == expected_changes

    def test_real_diff(self):
        diff = """--- a/elastic/datadog_checks/elastic/elastic.py
    +++ b/elastic/datadog_checks/elastic/elastic.py
    @@ -139,11 +139,17 @@ def _get_es_version(self):
            try:
                data = self._get_data(self._config.url, send_sc=False)
                raw_version = data['version']['number']
    +
                self.set_metadata('version', raw_version)
                # pre-release versions of elasticearch are suffixed with -rcX etc..
                # peel that off so that the map below doesn't error out
                raw_version = raw_version.split('-')[0]
                version = [int(p) for p in raw_version.split('.')[0:3]]
    +            if data['version'].get('distribution', '') == 'opensearch':
    +                # Opensearch API is backwards compatible with ES 7.10.0
    +                # https://opensearch.org/faq
    +                self.log.debug('OpenSearch version %s detected', version)
    +                version = [7, 10, 0]
            except AuthenticationError:
                raise
            except Exception as e:
    """
        expected_changes = {
            "elastic/datadog_checks/elastic/elastic.py": {
                "addition": [143, 149, 150, 151, 152, 153],
                "deletion": [],
                "delete_windows": [(139, 150)],
            },
        }
        assert parse_diff(diff) == expected_changes

    def test_real_complicated_diff(self):
        diff = '''diff --git a/nginx/datadog_checks/nginx/__init__.py b/nginx/datadog_checks/nginx/__init__.py
--- a/nginx/datadog_checks/nginx/__init__.py
+++ b/nginx/datadog_checks/nginx/__init__.py
@@ -2,6 +2,6 @@
 
 Nginx = nginx.Nginx
 
-__version__ = "1.1.0"
+__version__ = "1.2.0"
 
 __all__ = ['nginx']
diff --git a/nginx/datadog_checks/nginx/nginx.py b/nginx/datadog_checks/nginx/nginx.py
--- a/nginx/datadog_checks/nginx/nginx.py
+++ b/nginx/datadog_checks/nginx/nginx.py
@@ -5,6 +5,8 @@
 # stdlib
 import re
 import urlparse
+import time
+from datetime import datetime
 
 # 3rd party
 import requests
@@ -23,6 +25,20 @@
     'nginx.upstream.peers.responses.5xx'
 ]
 
+PLUS_API_ENDPOINTS = {
+    "nginx": [],
+    "http/requests": ["requests"],
+    "http/server_zones": ["server_zones"],
+    "http/upstreams": ["upstreams"],
+    "http/caches": ["caches"],
+    "processes": ["processes"],
+    "connections": ["connections"],
+    "ssl": ["ssl"],
+    "slabs": ["slabs"],
+    "stream/server_zones": ["stream", "server_zones"],
+    "stream/upstreams": ["stream", "upstreams"],
+}
+
 class Nginx(AgentCheck):
     """Tracks basic nginx metrics via the status module
     * number of connections
@@ -39,18 +55,32 @@ class Nginx(AgentCheck):
 
     """
     def check(self, instance):
+
         if 'nginx_status_url' not in instance:
             raise Exception('NginX instance missing "nginx_status_url" value.')
         tags = instance.get('tags', [])
 
-        response, content_type = self._get_data(instance)
-        self.log.debug(u"Nginx status `response`: {0}".format(response))
-        self.log.debug(u"Nginx status `content_type`: {0}".format(content_type))
+        url, ssl_validation, auth, use_plus_api, plus_api_version = self._get_instance_params(instance)
 
-        if content_type.startswith('application/json'):
-            metrics = self.parse_json(response, tags)
+        if not use_plus_api:
+            response, content_type = self._get_data(url, ssl_validation, auth)
+            self.log.debug(u"Nginx status `response`: {0}".format(response))
+            self.log.debug(u"Nginx status `content_type`: {0}".format(content_type))
+
+            if content_type.startswith('application/json'):
+                metrics = self.parse_json(response, tags)
+            else:
+                metrics = self.parse_text(response, tags)
         else:
-            metrics = self.parse_text(response, tags)
+            metrics = []
+            self._perform_service_check("/".join([url, plus_api_version]), ssl_validation, auth)
+            # These are all the endpoints we have to call to get the same data as we did with the old API
+            # since we can't get everything in one place anymore.
+
+            for endpoint, nest in PLUS_API_ENDPOINTS.iteritems():
+                response = self._get_plus_api_data(url, ssl_validation, auth, plus_api_version, endpoint, nest)
+                self.log.debug(u"Nginx Plus API version {0} `response`: {1}".format(plus_api_version, response))
+                metrics.extend(self.parse_json(response, tags))
 
         funcs = {
             'gauge': self.gauge,
@@ -62,13 +92,13 @@ def check(self, instance):
                 name, value, tags, metric_type = row
                 if name in UPSTREAM_RESPONSE_CODES_SEND_AS_COUNT:
                     func_count = funcs['count']
-                    func_count(name+"_count", value, tags)
+                    func_count(name + "_count", value, tags)
                 func = funcs[metric_type]
                 func(name, value, tags)
             except Exception as e:
                 self.log.error(u'Could not submit metric: %s: %s' % (repr(row), str(e)))
 
-    def _get_data(self, instance):
+    def _get_instance_params(self, instance):
         url = instance.get('nginx_status_url')
         ssl_validation = instance.get('ssl_validation', True)
 
@@ -76,6 +106,26 @@ def _get_data(self, instance):
         if 'user' in instance and 'password' in instance:
             auth = (instance['user'], instance['password'])
 
+        use_plus_api = instance.get("use_plus_api", False)
+        plus_api_version = str(instance.get("plus_api_version", 2))
+
+        return url, ssl_validation, auth, use_plus_api, plus_api_version
+
+    def _get_data(self, url, ssl_validation, auth):
+
+        r = self._perform_service_check(url, ssl_validation, auth)
+
+        body = r.content
+        resp_headers = r.headers
+        return body, resp_headers.get('content-type', 'text/plain')
+
+    def _perform_request(self, url, ssl_validation, auth):
+        r = requests.get(url, auth=auth, headers=headers(self.agentConfig),
+                         verify=ssl_validation, timeout=self.default_integration_http_timeout)
+        r.raise_for_status()
+        return r
+
+    def _perform_service_check(self, url, ssl_validation, auth):
         # Submit a service check for status page availability.
         parsed_url = urlparse.urlparse(url)
         nginx_host = parsed_url.hostname
@@ -84,9 +134,7 @@ def _get_data(self, instance):
         service_check_tags = ['host:%s' % nginx_host, 'port:%s' % nginx_port]
         try:
             self.log.debug(u"Querying URL: {0}".format(url))
-            r = requests.get(url, auth=auth, headers=headers(self.agentConfig),
-                             verify=ssl_validation, timeout=self.default_integration_http_timeout)
-            r.raise_for_status()
+            r = self._perform_request(url, ssl_validation, auth)
         except Exception:
             self.service_check(service_check_name, AgentCheck.CRITICAL,
                                tags=service_check_tags)
@@ -94,10 +142,31 @@ def _get_data(self, instance):
         else:
             self.service_check(service_check_name, AgentCheck.OK,
                                tags=service_check_tags)
+        return r
 
-        body = r.content
-        resp_headers = r.headers
-        return body, resp_headers.get('content-type', 'text/plain')
+    def _nest_payload(self, keys, payload):
+        # Nest a payload in a dict under the keys contained in `keys`
+        if len(keys) == 0:
+            return payload
+        else:
+            return {
+                keys[0]: self._nest_payload(keys[1:], payload)
+            }
+
+    def _get_plus_api_data(self, api_url, ssl_validation, auth, plus_api_version, endpoint, nest):
+        # Get the data from the Plus API and reconstruct a payload similar to what the old API returned
+        # so we can treat it the same way
+
+        url = "/".join([api_url, plus_api_version, endpoint])
+        payload = {}
+        try:
+            self.log.debug(u"Querying URL: {0}".format(url))
+            r = self._perform_request(url, ssl_validation, auth)
+            payload = self._nest_payload(nest, r.json())
+        except Exception as e:
+            self.log.exception("Error querying %s metrics at %s: %s", endpoint, url, e)
+
+        return payload
 
     @classmethod
     def parse_text(cls, raw, tags):
@@ -134,7 +203,10 @@ def parse_text(cls, raw, tags):
     def parse_json(cls, raw, tags=None):
         if tags is None:
             tags = []
-        parsed = json.loads(raw)
+        if isinstance(raw, dict):
+            parsed = raw
+        else:
+            parsed = json.loads(raw)
         metric_base = 'nginx'
         output = []
         all_keys = parsed.keys()
@@ -188,7 +260,19 @@ def _flatten_json(cls, metric_base, val, tags):
                 val = 0
             output.append((metric_base, val, tags, 'gauge'))
 
-        elif isinstance(val, (int, float)):
+        elif isinstance(val, (int, float, long)):
             output.append((metric_base, val, tags, 'gauge'))
 
+        elif isinstance(val, (unicode, str)):
+            # In the new Plus API, timestamps are now formatted strings, some include microseconds, some don't...
+            try:
+                timestamp = time.mktime(datetime.strptime(val, "%Y-%m-%dT%H:%M:%S.%fZ").timetuple())
+                output.append((metric_base, timestamp, tags, 'gauge'))
+            except ValueError:
+                try:
+                    timestamp = time.mktime(datetime.strptime(val, "%Y-%m-%dT%H:%M:%SZ").timetuple())
+                    output.append((metric_base, timestamp, tags, 'gauge'))
+                except ValueError:
+                    pass
+
         return output

'''
        expected_changes = {
            "nginx/datadog_checks/nginx/nginx.py": {
                "addition": [
                    9,
                    10,
                    29,
                    30,
                    31,
                    32,
                    33,
                    34,
                    35,
                    36,
                    37,
                    38,
                    39,
                    40,
                    41,
                    42,
                    59,
                    64,
                    66,
                    67,
                    68,
                    69,
                    70,
                    71,
                    72,
                    73,
                    74,
                    76,
                    77,
                    78,
                    79,
                    80,
                    81,
                    82,
                    83,
                    84,
                    96,
                    102,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                    117,
                    118,
                    119,
                    120,
                    121,
                    122,
                    123,
                    124,
                    125,
                    126,
                    127,
                    128,
                    129,
                    138,
                    146,
                    148,
                    149,
                    150,
                    151,
                    152,
                    153,
                    154,
                    155,
                    156,
                    157,
                    158,
                    159,
                    160,
                    161,
                    162,
                    163,
                    164,
                    165,
                    166,
                    167,
                    168,
                    169,
                    170,
                    207,
                    208,
                    209,
                    210,
                    264,
                    267,
                    268,
                    269,
                    270,
                    271,
                    272,
                    273,
                    274,
                    275,
                    276,
                    277,
                    278,
                ],
                "deletion": [
                    47,
                    48,
                    49,
                    51,
                    52,
                    54,
                    66,
                    72,
                    88,
                    89,
                    90,
                    99,
                    100,
                    101,
                    138,
                    192,
                ],
                "delete_windows": [
                    (5, 11),
                    (23, 29),
                    (39, 57),
                    (62, 75),
                    (76, 82),
                    (84, 93),
                    (94, 104),
                    (134, 141),
                    (188, 195),
                ],
            },
            "nginx/datadog_checks/nginx/__init__.py": {
                "addition": [6],
                "deletion": [6],
                "delete_windows": [(2, 8)],
            },
        }
        assert parse_diff(diff) == expected_changes
