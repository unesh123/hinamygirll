from hinaa_api.config import Settings


def test_new_names_reach_existing_adapters():
    s = Settings(_env_file=None, PLATFORM_EXPERIMENTAL_LABS_API_KEY='test-only',
                 PLATFORM_EXPERIMENTAL_LABS_BASE_URL='https://example.test/v1',
                 TREG_TO_API_KEY='test-treg', YOUCOM_API_BASE_URL='https://search.example.test')
    assert s.explabs_api_key.get_secret_value() == 'test-only'
    assert s.explabs_base_url == 'https://example.test/v1'
    assert s.treg_token.get_secret_value() == 'test-treg'
    assert s.youcom_base_url == 'https://search.example.test'


def test_gmi_dashboard_is_not_used_as_inference_endpoint():
    from hinaa_api.services import ProviderRouter
    s = Settings(_env_file=None, console_gmicloud_ai_api_key='test-key',
                 console_gmicloud_ai_api_key_base_url='https://console.gmicloud.ai/')
    assert s.active_gmi_base_url == 'https://api.gmi-serving.com/v1'
    provider = ProviderRouter(s).llm('gmi')
    assert provider.id == 'gmi'
    assert provider._model == s.gmi_model
