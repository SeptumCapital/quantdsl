import unittest
import os
import sys
from subprocess import Popen

from cassandra.cqlengine.management import drop_keyspace
from eventsourcing.domain.model.events import assert_event_handlers_empty

from eventsourcing.infrastructure.stored_events.cassandra_stored_events import create_cassandra_keyspace_and_tables

from quantdsl.application.main import get_quantdsl_app
from quantdsl.infrastructure.celery.tasks import CeleryQueueFacade
from quantdsl.application.with_cassandra import DEFAULT_QUANTDSL_CASSANDRA_KEYSPACE
from quantdsl.test_application import ApplicationTestCase, ContractValuationTests


class TestApplicationWithCassandraAndCelery(ApplicationTestCase, ContractValuationTests):

    skip_assert_event_handers_empty = True  # Do it in setup/teardown class.

    @classmethod
    def setUpClass(cls):
        # Set up the application and the workers for the class, not each test, otherwise they drag.
        assert_event_handlers_empty()
        os.environ['QUANTDSL_BACKEND'] = 'cassandra'

        # Create Cassandra keyspace and tables.
        cls._app = get_quantdsl_app(call_evaluation_queue=CeleryQueueFacade())
        create_cassandra_keyspace_and_tables(DEFAULT_QUANTDSL_CASSANDRA_KEYSPACE)

        # Check we've got a path to the 'celery' command line program (hopefully it's next to this python executable).
        celery_script_path = os.path.join(os.path.dirname(sys.executable), 'celery')
        assert os.path.exists(celery_script_path), celery_script_path

        if not hasattr(cls, 'is_celeryworker_started'):
            cls.is_celery_worker_started = True
            # Check the example task returns correct result (this assumes the celery worker IS running).
            # - invoke a celery worker process as a subprocess
            worker_cmd = [celery_script_path, 'worker', '-A', 'quantdsl.infrastructure.celery.tasks', '-P', 'eventlet', '-c', '1000', '-l', 'info']
            cls.worker = Popen(worker_cmd)

    @classmethod
    def tearDownClass(cls):
        # Drop the keyspace.
        drop_keyspace(DEFAULT_QUANTDSL_CASSANDRA_KEYSPACE)   # Drop keyspace before closing the application.
        cls._app.close()
        assert_event_handlers_empty()

        os.environ.pop('QUANTDSL_BACKEND')

        # Shutdown the celery worker.
        # - its usage as a context manager causes a wait for it to finish
        # after it has been terminated, and its stdin and stdout are closed
        with getattr(cls, 'worker') as worker:
            if worker is not None:
                worker.terminate()

    def setup_application(self):
        self.app = self._app  # Makes it available for each test.

    def tearDown(self):
        self.app = None  # Stops is being closed at the end of each test.
        super(TestApplicationWithCassandraAndCelery, self).tearDown()

#     def test_generate_valuation_swing_option(self):
#         specification = """
# def Swing(start_date, end_date, underlying, quantity):
#     if (quantity != 0) and (start_date < end_date):
#         return Choice(
#             Swing(start_date + TimeDelta('1d'), end_date, underlying, quantity-1) + Fixing(start_date, underlying),
#             Swing(start_date + TimeDelta('1d'), end_date, underlying, quantity)
#         )
#     else:
#         return 0
#
# Swing(Date('2011-01-01'), Date('2011-01-05'), Market('NBP'), 3)
# """
#         self.assert_contract_value(specification, 30.2075, expected_call_count=15)

if __name__ == '__main__':
    unittest.main()