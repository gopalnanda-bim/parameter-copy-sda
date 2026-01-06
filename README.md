# parameter-copy-sda

This tool allows Revit users to copy parameter values from a single source element to multiple target elements, even across different families or categories.

Unlike generic parameter copy tools, it automatically detects and presents only those parameters that exist on the source and on all selected targets, significantly reducing errors and preventing invalid assignments.

Key features

Source → multi-target workflow with toggle selection

Shows common parameters only (intersection across all elements)

Supports String, Integer, Double, and ElementId parameters

Skips read-only, missing, or incompatible parameters safely

Clear summary report after execution

Designed for real-world BIM models and mixed-family selections

Typical use cases

Copying height or installation metadata across devices

Synchronizing MEP room information between elements

Standardizing shared parameters across different families
