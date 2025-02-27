import unittest
from mongo import client
from server import app

class BaseTestClass(unittest.TestCase):
    def setUp(self):

        # set up any variables or configurations needed for your tests
        self.client = app.test_client()

    def tearDown(self):
        # tear down any variables or configurations set up in setUp() 
        client.drop_database('testregistry')
