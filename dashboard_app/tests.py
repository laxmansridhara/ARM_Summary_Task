from django.test import TestCase
from .models import Papers, Authors, Users, Keywords, Author_Papers, Researcher, Users_Keywords, Keywords_Paper
from .const import Config
from datetime import date


class PapersModelTest(TestCase):
    def setUp(self):
        self.paper = Papers.objects.create(
            doi="10.1234/example-doi",
            title="Test Paper",
            publishing_year=2025,
            abstract="This is a test abstract",
            citations_count=42,
            link="https://example.com/test-paper"
        )

    def test_paper_creation(self):
        self.assertEqual(self.paper.title, "Test Paper")
        self.assertEqual(self.paper.citations_count, 42)

    def test_doi_link(self):
        Config.DOI_PREFIX = "https://doi.org/"
        self.assertEqual(self.paper.paper_doi_link(), "https://doi.org/10.1234/example-doi")


class AuthorsModelTest(TestCase):
    def setUp(self):
        self.author = Authors.objects.create(
            id=1,
            name="Jane Doe",
            orcid="0000-0002-1825-0097"
        )

    def test_author_creation(self):
        self.assertEqual(self.author.name, "Jane Doe")
        self.assertEqual(self.author.orcid, "0000-0002-1825-0097")


class UsersModelTest(TestCase):
    def setUp(self):
        self.user = Users.objects.create(
            id=1,
            name="Alice",
            created=date.today(),
            email="alice@example.com",
            password="securepassword",
            acc_type=Users.AccountType.MEMBER,
            username="alice123"
        )

    def test_user_creation(self):
        self.assertEqual(self.user.username, "alice123")
        self.assertEqual(self.user.acc_type, Users.AccountType.MEMBER)


class KeywordsModelTest(TestCase):
    def setUp(self):
        self.keyword = Keywords.objects.create(
            id=1,
            keyword="Artificial Intelligence"
        )

    def test_keyword_creation(self):
        self.assertEqual(self.keyword.keyword, "Artificial Intelligence")


class RelationsTest(TestCase):
    def setUp(self):
        self.paper = Papers.objects.create(
            doi="10.1234/example-rel",
            title="Relational Paper",
            publishing_year=2025,
            abstract="Testing relations",
            citations_count=10,
            link="https://example.com/rel-paper"
        )
        self.author = Authors.objects.create(id=1, name="John Doe")
        self.user = Users.objects.create(
            id=1,
            name="Bob",
            created=date.today(),
            email="bob@example.com",
            password="securepassword",
            acc_type=Users.AccountType.RESEARCHER,
            username="bob123"
        )
        self.keyword = Keywords.objects.create(id=1, keyword="Deep Learning")

    def test_author_paper_relation(self):
        rel = Author_Papers.objects.create(doi=self.paper, author_id=self.author)
        self.assertEqual(rel.doi.title, "Relational Paper")
        self.assertEqual(rel.author_id.name, "John Doe")

    def test_user_keyword_relation(self):
        rel = Users_Keywords.objects.create(user_id=self.user, keyword_id=self.keyword)
        self.assertEqual(rel.user_id.username, "bob123")
        self.assertEqual(rel.keyword_id.keyword, "Deep Learning")

    def test_keyword_paper_relation(self):
        rel = Keywords_Paper.objects.create(doi=self.paper, keyword_id=self.keyword)
        self.assertEqual(rel.doi.title, "Relational Paper")
        self.assertEqual(rel.keyword_id.keyword, "Deep Learning")

    def test_researcher_relation(self):
        rel = Researcher.objects.create(user_id=self.user, author_id=self.author)
        self.assertEqual(rel.user_id.username, "bob123")
        self.assertEqual(rel.author_id.name, "John Doe")
