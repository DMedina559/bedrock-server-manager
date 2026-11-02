Scheduler API
=============

Read task definitions and bounded run metadata from the unified ``TaskDefinition``
registry. Administrator HTTP endpoints own schedule changes; plugins register
namespaced handlers using ``@scheduled_task``, ``scheduled_apis``, or
``api.runtime.register_api_task``.

.. automodule:: bedrock_server_manager.api.scheduler
   :members:
   :member-order: bysource
