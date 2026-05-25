from fastapi import HTTPException
import pytest

from voice.auth.token import verify_token


class TestVerifyToken:
    def test_no_token_configured_allows(self):
        import voice.config
        original = voice.config.settings.api_token
        voice.config.settings.api_token = None
        try:
            verify_token(None)
            verify_token("anything")
        finally:
            voice.config.settings.api_token = original

    def test_valid_token_allows(self):
        import voice.config
        original = voice.config.settings.api_token
        voice.config.settings.api_token = "secret"
        try:
            verify_token("Bearer secret")
        finally:
            voice.config.settings.api_token = original

    def test_invalid_token_raises(self):
        import voice.config
        original = voice.config.settings.api_token
        voice.config.settings.api_token = "secret"
        try:
            with pytest.raises(HTTPException, match="401"):
                verify_token("Bearer wrong")
            with pytest.raises(HTTPException, match="401"):
                verify_token(None)
            with pytest.raises(HTTPException, match="401"):
                verify_token("wrong format")
        finally:
            voice.config.settings.api_token = original
