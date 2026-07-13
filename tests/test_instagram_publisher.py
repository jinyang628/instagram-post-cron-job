import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

import instagram_publisher as publisher


class InstagramPublisherTests(unittest.TestCase):
    @patch("instagram_publisher.time.sleep")
    @patch("instagram_publisher.request_json")
    def test_publish_waits_for_container_then_publishes(self, request_json, _sleep):
        request_json.side_effect = [
            {"id": "container-1"},
            {"status_code": "IN_PROGRESS"},
            {"status_code": "FINISHED"},
            {"id": "media-1"},
        ]

        media_id = publisher.publish_image(
            image_url="https://example.com/cucumber.jpg",
            caption="cucumber",
            access_token="token",
            instagram_user_id="123",
            graph_api_version="v25.0",
        )

        self.assertEqual("media-1", media_id)
        self.assertEqual(4, request_json.call_count)

    @patch("instagram_publisher.urllib.request.urlopen")
    def test_request_json_reports_graph_error(self, urlopen):
        error_body = MagicMock()
        error_body.read.return_value = json.dumps({"error": {"message": "Bad token"}}).encode()
        error_body.__enter__.return_value = error_body
        urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 400, "Bad Request", {}, error_body
        )

        with self.assertRaisesRegex(publisher.InstagramError, "Bad token"):
            publisher.request_json("https://example.com", {"a": "b"})


if __name__ == "__main__":
    unittest.main()
