# Guide de prise en main

Le dossier contient une solution de repli démontrable, prévue par le sujet.
Les données sont fictives : nous n'avons pas établi l'accès à une API REST MaStR
qui fournisse exactement les événements demandés.

## Ce qui fonctionne localement

Le collecteur lit deux pages d'exemples, garde les événements allemands d'au moins
110 kV, contrôle les dates, transforme les coordonnées et enregistre les résultats.
Une deuxième exécution ne crée aucun doublon. Les données incorrectes sont consignées
dans le rapport, et une localisation manquante reste vide avec un avertissement.

Lis README.md pour lancer la démonstration. Le code de sortie 2 est attendu :
trois enregistrements de l'exemple contiennent volontairement des erreurs.

## Ce qu'il faut encore vérifier avant de présenter une solution en production

- L'adresse exacte de l'API et les champs qui prouvent les événements recherchés.
- Le schéma attendu par IRIS et le périmètre géographique.
Le test réel sous PostgreSQL 16 / PostGIS 3.4 a réussi le 28 octobre 2026 :
**1 passed en 12,34 secondes**, selon la capture du terminal fournie.
Les 44 autres tests avaient déjà réussi lors de la vérification initiale.

SOURCE_ASSESSMENT.md contient les références et les questions précises.
VALIDATION.md distingue les tests effectués de ceux qui restent à exécuter.

Pour expliquer le projet en entretien : parcours source.py, pipeline.py, storage.py,
puis les tests. Les décisions essentielles sont de ne pas confondre une installation
avec une demande de raccordement, de conserver la traçabilité, et de rendre les
relances sûres.

Le projet a été publié par l'utilisateur sur GitHub. Aucun email n'a été envoyé
par l'assistant. Les documents locaux mis à jour doivent encore être reportés sur GitHub.

