from django.db import models
from .const import Config


#----------------Main Tables----------------------#
class Papers (models.Model):
    doi = models.CharField(max_length=500, null=False, blank=False, primary_key=True)
    title = models.CharField(max_length=500, null=False, blank=False)
    publishing_year = models.IntegerField(null=False)


    abstract = models.TextField()
    citations_count = models.IntegerField(null=False)
    link = models.URLField(max_length=2000,null=False, blank=False)
    paper_type = models.CharField(max_length=20, null=False, blank=False)
    
    def paper_doi_link(self):
        if not Config.DOI_PREFIX:
            return -1
        elif not self.doi:
            return -2
        elif Config.DOI_PREFIX and self.doi:
            return Config.DOI_PREFIX + self.doi
    
    
class Authors(models.Model):
    id = models.CharField(max_length=20,null=False, unique=True, primary_key=True)
    name = models.CharField(max_length=150, blank=False, null=False)
    orcid = models.CharField(max_length=20, unique=False, null=True, blank=True)

    
    
class Users(models.Model):
    class AccountType(models.TextChoices):
        MEMBER = "MEMBER", "Member"
        RESEARCHER = "RESEARCHER", "Researcher"
        ADMIN = "ADMIN", "Admin"
        
    id = models.IntegerField(null=False, unique=True, primary_key=True)
    name = models.CharField(max_length=150, blank=False, null=False)
    created = models.DateField(null=False, blank=False)
    email = models.EmailField(null=False, blank=False)
    password = models.CharField(max_length=256, null=False, blank=False)
    acc_type = models.CharField(max_length=50, null=False, blank=False, choices=AccountType.choices, default=AccountType.MEMBER)
    username = models.CharField(max_length=150, null=False, blank=False, unique=True)
    
    
class Keywords(models.Model):
    id = models.CharField(max_length=20, null=False, unique=True, primary_key=True)
    keyword = models.CharField(max_length=200, null=False, blank=False, unique=True)
    
    
##------------------Tables for junctions------------------------------##
class Author_Papers(models.Model):
    doi = models.ForeignKey(Papers, on_delete=models.CASCADE)
    author_id = models.ForeignKey(Authors, on_delete=models.CASCADE)
    class Meta:
        unique_together = ("doi", "author_id")
    
    
class Researcher(models.Model):
    user_id = models.ForeignKey(Users, on_delete=models.CASCADE)
    author_id = models.ForeignKey(Authors, on_delete=models.CASCADE)
    
   
    
class Users_Keywords(models.Model):
    keyword_id = models.ForeignKey(Keywords, on_delete=models.CASCADE)
    user_id = models.ForeignKey(Users, on_delete=models.CASCADE)
    
    
class Keywords_Paper(models.Model):
    keyword_id = models.ForeignKey(Keywords, on_delete=models.CASCADE)
    doi = models.ForeignKey(Papers, on_delete=models.CASCADE)
    class Meta:
        unique_together = ("doi", "keyword_id")
    
