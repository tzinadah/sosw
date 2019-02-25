__all__ = ['TaskManager']
__author__ = "Nikolay Grishchenko"
__version__ = "1.0"

import boto3
import json
import logging
import os
import time

from collections import defaultdict
from typing import Dict, List, Optional

from sosw.components.benchmark import benchmark
from sosw.app import Processor


logger = logging.getLogger()
logger.setLevel(logging.INFO)


class TaskManager(Processor):
    DEFAULT_CONFIG = {
        'init_clients':                ['DynamoDb'],
        'dynamo_db_config':            {
            'table_name':       'sosw_tasks',
            'index_greenfield': 'sosw_tasks_greenfield',
            'row_mapper':       {
                'task_id':      'S',
                'worker_id':    'S',
                'created_at':   'N',
                'completed_at': 'N',
                'greenfield':   'N',
                'attempts':     'N',
            },
            'required_fields':  ['task_id', 'worker_id', 'created_at', 'greenfield'],
        },
        'greenfield_invocation_delta': 31557600,  # 1 year.
        'greenfield_field_name':       'greenfield',  # This is a pseudofield to track status and order of tasks as ints
    }


    def create_task(self, **kwargs):
        raise NotImplementedError


    def invoke_task(self, task_id: str):
        raise NotImplementedError


    def close_task(self, task_id: str):
        raise NotImplementedError


    def _get_max_univoked_greenfield(self) -> int:
        """
        Returns the current date + configurable delta for greenfield not yet invoked.
        """

        return int(time.time()) + self.config['greenfield_invocation_delta']


    def get_next_for_worker(self, worker_id: int, cnt: int = 1) -> List[Dict]:
        """
        Fetch the next in queue tasks for the Worker.

        :param worker_id:   ID of the Worker from sosw config.
        :param cnt:         Optional number of Tasks to fetch.
        """

        # Maximum value to identify the task as available for invocation (either new, or ready for retry).
        max_greenfield = self._get_max_univoked_greenfield()

        result = self.dynamo_db_client.get_by_query({'worker_id': worker_id, 'greenfield': max_greenfield},
                                                    table_name=self.config['dynamo_db_config']['table_name'],
                                                    index_name=self.config['dynamo_db_config']['index_greenfield'],
                                                    strict=True,
                                                    max_items=cnt,
                                                    comparisons={
                                                        self.config['dynamo_db_config']['greenfield_field_name']: '<'
                                                    })
        logger.debug(f"get_next_for_worker() received: {result}")

        return result


    def get_workers(self):
        return [1]


    def __call__(self, event):
        workers = self.get_workers()

        tasks_to_process = []
        for worker_id in workers:
            tasks_to_process = self.get_next_for_worker(worker_id=worker_id)
            logger.info(tasks_to_process)

        return tasks_to_process
