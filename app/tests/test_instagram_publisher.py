import json
import unittest
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

from PIL import Image

from app import instagram_publisher as publisher
from app import caption


class InstagramPublisherTests(unittest.TestCase):
    @patch("app.caption.urllib.request.urlopen")
    def test_generate_dad_joke_uses_openrouter_free_model(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = BytesIO(
            json.dumps(
                {"choices": [{"message": {"content": "A freshly generated dad joke."}}]}
            ).encode()
        )
        urlopen.return_value = response

        joke = caption.generate_dad_joke("openrouter-token")

        self.assertEqual("A freshly generated dad joke.", joke)
        request = urlopen.call_args.args[0]
        self.assertEqual(caption.OPENROUTER_URL, request.full_url)
        self.assertEqual("Bearer openrouter-token", request.get_header("Authorization"))
        payload = json.loads(request.data)
        self.assertEqual("openrouter/free", payload["model"])

    @patch("app.caption.urllib.request.urlopen")
    def test_generate_dad_joke_rejects_missing_content(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = BytesIO(json.dumps({"choices": []}).encode())
        urlopen.return_value = response

        with self.assertRaisesRegex(publisher.CaptionGenerationError, "text caption"):
            caption.generate_dad_joke("openrouter-token")

    @patch("app.instagram_publisher.STATE_FILE")
    @patch("app.instagram_publisher.publish_post", return_value="media-1")
    @patch("app.instagram_publisher.generate_dad_joke", return_value="Generated joke")
    @patch(
        "app.instagram_publisher.upload_generated_image",
        return_value="https://res.cloudinary.com/demo/image/upload/post.jpg",
    )
    @patch("app.instagram_publisher.generate_image")
    @patch("app.instagram_publisher.required_env")
    def test_main_uses_generated_joke_as_image_prompt_and_caption(
        self,
        required_env,
        generate_image,
        upload_generated_image,
        generate_dad_joke,
        publish_post,
        state_file,
    ):
        state_file.exists.return_value = False
        required_env.side_effect = lambda name: {
            "OPEN_ROUTER_API_KEY": "openrouter-token",
            "INSTAGRAM_ACCESS_TOKEN": "instagram-token",
            "INSTAGRAM_USER_ID": "123",
            "HF_TOKEN": "hf-token",
            "CLOUDINARY_CLOUD_NAME": "cloud-name",
            "CLOUDINARY_API_KEY": "cloudinary-key",
            "CLOUDINARY_API_SECRET": "cloudinary-secret",
        }[name]

        result = publisher.main()

        self.assertEqual(0, result)
        generate_dad_joke.assert_called_once_with(api_key="openrouter-token")
        generate_image.assert_called_once_with(api_key="hf-token", prompt="Generated joke")
        self.assertEqual("Generated joke", publish_post.call_args.kwargs["caption"])
        self.assertEqual(
            "https://res.cloudinary.com/demo/image/upload/post.jpg",
            publish_post.call_args.kwargs["image_url"],
        )
        upload_generated_image.assert_called_once_with(
            generate_image.return_value,
            cloud_name="cloud-name",
            api_key="cloudinary-key",
            api_secret="cloudinary-secret",
        )
        state_file.write_text.assert_called_once()

    @patch("app.instagram_publisher.urllib.request.urlopen")
    def test_upload_generated_image_returns_cloudinary_secure_url(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = BytesIO(
            json.dumps(
                {"secure_url": "https://res.cloudinary.com/demo/image/upload/post.jpg"}
            ).encode()
        )
        urlopen.return_value = response

        image_url = publisher.upload_generated_image(
            Image.new("RGB", (2, 2), "green"),
            cloud_name="demo",
            api_key="cloudinary-key",
            api_secret="cloudinary-secret",
        )

        self.assertEqual("https://res.cloudinary.com/demo/image/upload/post.jpg", image_url)
        request = urlopen.call_args.args[0]
        self.assertEqual("https://api.cloudinary.com/v1_1/demo/image/upload", request.full_url)
        self.assertIn(b'name="file"; filename="post.jpg"', request.data)

    @patch("app.instagram_publisher.time.sleep")
    @patch("app.instagram_publisher.request_json")
    def test_publish_waits_for_container_then_publishes(self, request_json, _sleep):
        request_json.side_effect = [
            {"id": "container-1"},
            {"status_code": "IN_PROGRESS"},
            {"status_code": "FINISHED"},
            {"id": "media-1"},
        ]

        media_id = publisher.publish_post(
            image_url="https://example.com/cucumber.jpg",
            caption="cucumber",
            access_token="token",
            instagram_user_id="123",
            graph_api_version="v25.0",
        )

        self.assertEqual("media-1", media_id)
        self.assertEqual(4, request_json.call_count)
        self.assertEqual(
            "https://graph.instagram.com/v25.0/123/media",
            request_json.call_args_list[0].args[0],
        )

    @patch("app.instagram_publisher.urllib.request.urlopen")
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
