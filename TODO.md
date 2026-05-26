# TODO

## VAD — Voice Activity Detection

Adicionar VAD no whisper-server para filtrar música de fundo e ruído, transcrevendo apenas trechos com voz.

- Baixar modelo VAD: `./models/download-vad-model.sh silero-v6.2.0`
- Iniciar servidor com:
  ```bash
  whisper-server -m models/ggml-base.bin -l pt \
    --vad \
    --vad-model models/ggml-silero-v6.2.0.bin \
    --suppress-nst \
    --no-speech-thold 0.6 \
    --host 0.0.0.0 --port 19000
  ```
- Docs: https://github.com/ggml-org/whisper.cpp#voice-activity-detection-vad
