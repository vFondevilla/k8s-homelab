# Tinkerbell examples

These examples define one Hardware resource, one Ubuntu template, and one workflow.

Argo does not reconcile this directory. The examples are not part of the Tinkerbell platform overlay.

## Files

- `01-hardware.yaml` contains placeholder hardware, network, and disk values.
- `02-template-ubuntu.yaml` contains the image-to-disk workflow template.
- `03-workflow.yaml` connects the example hardware to the template.

## Use

CAUTION: Do not apply these resources to a production machine. The workflow erases and replaces the selected disk contents.

Before you apply `01-hardware.yaml`, replace every example hardware and network value.

Before you apply `02-template-ubuntu.yaml`, replace `REPLACE_WITH_IMAGE_SERVER` with a valid image server.

Before you apply `03-workflow.yaml`, make sure that the hardware name, template name, and MAC address are correct.

The Tinkerbell component is paused. Make sure that the required CRDs exist before you use these examples.
