from django.contrib import admin

from .models import Clue, GameSession, Guess

admin.site.register(Clue)
admin.site.register(GameSession)
admin.site.register(Guess)
