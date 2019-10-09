import unittest


class TestImports(unittest.TestCase):
    def test_import_rse(self):
        import rse

    def test_import_controllers(self):
        import rse.controllers

    def test_import_rax(self):
        import rse.rax

    @unittest.expectedFailure
    def test_import_wsgi_app(self):
        # configuration needs to be fixed before
        # this will pass properly
        from rse.wsgi import app
