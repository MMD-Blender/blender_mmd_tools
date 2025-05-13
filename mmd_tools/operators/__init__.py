# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

from .add_mesh_for_rigidbody import AddMeshForRigidbodyOperator

def register():
    AddMeshForRigidbodyOperator.register()

def unregister():
    AddMeshForRigidbodyOperator.unregister()
