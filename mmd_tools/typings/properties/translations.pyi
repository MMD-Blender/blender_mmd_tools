# -*- coding: utf-8 -*-
# Copyright 2024 MMD Tools authors
# This file is part of MMD Tools.

from typing import List

import bpy

class MMDTranslationElement:
    type: str
    object: bpy.types.Object
    data_path: str
    name: str
    name_j: str
    name_e: str

class MMDTranslationElementIndex(bpy.types.PropertyGroup):
    value: int

class MMDTranslation:
    id_data: bpy.types.Object
    translation_elements: List[MMDTranslationElement]
    filtered_translation_element_indices_active_index: int
    filtered_translation_element_indices: List[MMDTranslationElementIndex]

    filter_japanese_blank: bool
    filter_english_blank: bool
    filter_restorable: bool
    filter_selected: bool
    filter_visible: bool
    filter_types: str

    dictionary: str

    batch_operation_target: str

    batch_operation_script_preset: str

    batch_operation_script: str
