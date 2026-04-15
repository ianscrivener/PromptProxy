from gateway.config import load_runtime_config, resolve_path


def test_load_runtime_config_reads_yaml_and_env(tmp_path, monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "gateway_host: 0.0.0.0",
                "gateway_port: 9001",
                "gateway_version: 9.9.9",
                "log_backends:",
                "  - jsonl",
                "log_exclude_fields:",
                "  - backend_params",
                "jsonl_path: logs/custom.jsonl",
                "image_output_path: test_image_output",
                "static_image_base_url: http://127.0.0.1:9001/images",
                "fal_api_base_url: https://queue.fal.run",
                "request_timeout_seconds: 45",
            ]
        ),
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text("FAL_KEY=test-fal-key\n", encoding="utf-8")

    runtime = load_runtime_config(config_path=config_path, env_file=env_path)

    assert runtime.app.gateway_host == "0.0.0.0"
    assert runtime.app.gateway_port == 9001
    assert runtime.app.gateway_version == "9.9.9"
    assert runtime.app.log_backends == ["jsonl"]
    assert runtime.app.log_exclude_fields == ["backend_params"]
    assert runtime.secrets.fal_key == "test-fal-key"
    assert resolve_path(runtime.app.jsonl_path, runtime.project_root) == (tmp_path / "logs/custom.jsonl").resolve()
