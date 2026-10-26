from unittest import TestCase
import json
from app.review import parse_review


class ReviewTests(TestCase):
    def test_invalid_review_never_implies_approval(self):
        self.assertEqual(parse_review('I finished')['verdict'],'needs_review')

    def test_approval_with_blocking_findings_requires_changes(self):
        result=parse_review(json.dumps({'verdict':'approved','summary':'Found bug','findings':[{'severity':'high','path':'app.js','line':5,'message':'Bug'}]}))
        self.assertEqual(result['verdict'],'changes_requested')

    def test_valid_review_is_structured_and_bounded(self):
        self.assertEqual(parse_review('{"verdict":"approved","summary":"Reviewed","findings":[]}')['verdict'],'approved')
        self.assertEqual(parse_review(json.dumps({'verdict':'approved','summary':'x'*4000,'findings':[]}))['verdict'],'needs_review')
