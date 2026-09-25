"""Nodes of {{ project.name }}. Test in the sandboxed studio: sos-studio node-add <path or git url>."""


class Invert:
    """Example node: inverts an image (IMAGE tensors are floats in 0..1, shape [B, H, W, C])."""

    CATEGORY = "{{ project.name }}"
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}}

    def run(self, image):
        return (1.0 - image,)


NODE_CLASS_MAPPINGS = {"{{ project.package }}.Invert": Invert}
NODE_DISPLAY_NAME_MAPPINGS = {"{{ project.package }}.Invert": "Invert ({{ project.name }})"}
