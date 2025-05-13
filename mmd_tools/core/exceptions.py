# Copyright 2016 MMD Tools authors
# This file is part of MMD Tools.

# Module for custom exceptions


class MaterialNotFoundError(KeyError):
    """Exception raised when a material is not found in the scene"""

    def __init__(self, *args: object) -> None:
        """Constructor for MaterialNotFoundError"""
        super().__init__(*args)
