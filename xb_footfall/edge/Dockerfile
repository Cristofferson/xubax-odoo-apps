# xb_footfall edge CV agent.
# Base on the official ultralytics CPU image (bundles torch CPU + opencv); for a
# Jetson/CUDA box swap to ultralytics/ultralytics:latest (GPU) and set device: "0".
FROM ultralytics/ultralytics:latest-cpu

WORKDIR /edge
# pin the weights into the image so first run needs no download on the store LAN
RUN python3 -c "from ultralytics import YOLO; YOLO('yolo11n.pt')" || true

COPY counter.py calibrate.py ./
# config.yaml is mounted at runtime (keeps the token out of the image)

ENV XBF_CONFIG=/edge/config.yaml
ENTRYPOINT ["python3", "counter.py"]
