# Modelos de rosto

Ambos vêm do **OpenCV Zoo** (https://github.com/opencv/opencv_zoo) e rodam via `cv2.FaceDetectorYN` / `cv2.FaceRecognizerSF`.

| Arquivo | Origem | Uso | Licença |
|---|---|---|---|
| `yunet.onnx` | `face_detection_yunet_2023mar.onnx` (YuNet, Shiqi Yu et al.) | detectar rostos e 5 pontos de referência | MIT |
| `sface.onnx` | `face_recognition_sface_2021dec.onnx` (SFace, Zhong et al.) | comparar rostos (agrupar pessoas; teste de reconhecimento) | Apache-2.0 |

Se faltarem, `scripts/setup_check.py` baixa de:
- https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
- https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx

Os modelos servem para **detectar e agrupar rostos**, não para dizer quem é uma pessoa.
