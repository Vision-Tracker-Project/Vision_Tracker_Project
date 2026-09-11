"""Export a trained torchreid OSNet checkpoint; run on a development machine."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", required=True, help="Trained osnet_x0_25 checkpoint")
    parser.add_argument("--output", default="models/osnet_x0_25.onnx")
    args = parser.parse_args()
    import torch
    import torchreid

    # Refuse incomplete checkpoints instead of exporting random feature layers.
    model = torchreid.models.build_model(name="osnet_x0_25", num_classes=1000,
                                        pretrained=False, use_gpu=False)
    checkpoint = torch.load(args.weights, map_location="cpu", weights_only=True)
    state = checkpoint.get("state_dict", checkpoint)
    state = {k.removeprefix("module."): v for k, v in state.items()
             if not k.removeprefix("module.").startswith("classifier.")}
    result = model.load_state_dict(state, strict=False)
    missing = [k for k in result.missing_keys if not k.startswith("classifier.")]
    if missing or result.unexpected_keys:
        raise RuntimeError(f"Incompatible OSNet checkpoint: {missing}, {result.unexpected_keys}")
    model.eval()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(model, torch.zeros(1, 3, 256, 128), str(output),
                      input_names=["images"], output_names=["embeddings"],
                      opset_version=12)
    print(output)


if __name__ == "__main__":
    main()
