# PV Retenus – Audience Interpro et SVE

Ce dépôt contient les fichiers liés au suivi de l’audience interprofessionnelle de la CGT,
notamment les bases de données issues des PV retenus.

## 🗄️ Contenu
- **`papcse.db`** : base de données SQLite utilisée pour l’analyse des PV CSE et SVE.
  Ce fichier n’est pas versionné dans Git pour des raisons de taille,
  mais il est disponible en téléchargement via les *Releases*.

## 🧭 Découvrir la plateforme

La page d’accueil `/` rassemble désormais la vocation de l’outil « PAP/CSE · Tableau de bord » :

- **Héros introductif** mettant en avant les actions principales (calendrier +1000, recherche SIRET,
  administration) pour engager rapidement les équipes.
- **Cartes de fonctionnalités** décrivant les modules clés (Tableau de bord, Invitations PAP,
  Ciblages, Recherche SIRET) avec des liens directs.
- **Parcours PAP → PV** et **calendrier C5** pour visualiser la continuité entre invitations,
  votes et échéances à venir.
- **Ressources et FAQ** centralisées pour accompagner l’import des données et la maintenance.

👉 L’ancienne URL `/presentation` redirige automatiquement vers cette page consolidée.

📦 **Téléchargement direct :**
[👉 Télécharger la dernière version (.db)](https://github.com/quentin12200/outilspapv2/releases/latest)

ℹ️ **Où placer le fichier ?** Déposez `papcse.db` à la racine du dépôt (au même niveau
que ce README) ou mettez à jour la variable d’environnement `DATABASE_URL` pour pointer
vers son emplacement.

## 🔐 Vérification d’intégrité
Pour vérifier que le fichier téléchargé n’a pas été altéré, comparez le SHA-256 :

```bash
sha256sum papcse.db
# 36f5a979939849c7429d2ea3f06d376de3485dc645b59daf26b2be2eb866d6b8  papcse.db
```

👉 **Déploiement :** l’application calcule cette empreinte au démarrage si la variable
`DB_SHA256` est renseignée. Par défaut, elle continue à fonctionner même si le hash ne
correspond plus (par exemple après un enrichissement local). Pour retrouver un blocage
strict en cas d’écart, définissez `DB_FAIL_ON_HASH_MISMATCH=1` dans vos variables
d’environnement.

## 🌐 Utilisation de l'API Sirene

Les recherches SIRET réalisées depuis la page « Recherche de SIRET » s'appuient sur l'API Sirene de l'INSEE.
Pour éviter les erreurs 401/403 et bénéficier d'un débit confortable, ajoutez un jeton Bearer
dans la variable d'environnement `SIRENE_API_TOKEN` (ou `SIRENE_API_KEY`) sur votre instance Railway.

## ❓ Foire aux questions

### « Codex ne prend actuellement pas en charge la mise à jour des demandes d’extraction en dehors de Codex. Veuillez créer une nouvelle demande d’extraction », qu’est-ce que cela signifie ?

Ce message apparaît lorsque l’assistant n’a pas la possibilité de modifier une *pull request* GitHub existante.
Pour publier un correctif, il faut donc créer une nouvelle branche locale, y committer les changements,
et ouvrir une nouvelle *pull request* correspondante sur GitHub. L’ancienne PR reste intacte, et la nouvelle
contiendra les ajustements supplémentaires souhaités.

💡 **Pourquoi le message revient-il malgré tout ?** L’avertissement réapparaît à chaque fois que l’on tente malgré
tout de mettre à jour l’ancienne PR. C’est un comportement attendu : tant que l’on reste sur la même branche ou que
l’on essaie de pousser vers la PR historique, l’assistant ne peut pas l’éditer et répète donc le message. Il faut
ignorer cet avertissement et poursuivre la création d’une nouvelle PR.

✅ **Quand disparaît-il ?** Dès que vous poussez vos modifications sur une nouvelle branche et que vous créez une PR
distincte, l’avertissement n’est plus affiché pour cette série de changements.

🛑 **Que faire de l’ancienne PR ?** Si elle n’a plus lieu d’être, fermez-la manuellement dans GitHub pour éviter toute
confusion. Les discussions et commits y restent consultables, mais seules les nouvelles branches pourront accueillir
vos correctifs.

👩‍💻 **Étapes type côté Git :**

1. Mettre à jour la branche de travail : `git pull origin main` (ou la branche cible de votre PR).
2. Créer et basculer sur une nouvelle branche : `git checkout -b fix/invitations-table`.
3. Apporter les modifications souhaitées puis les valider :
   ```bash
   git add .
   git commit -m "Corrige les invitations PAP"
   ```
4. Pousser la branche sur votre dépôt GitHub : `git push origin fix/invitations-table`.
5. Depuis l’interface GitHub, ouvrir une nouvelle *pull request* en sélectionnant la branche tout juste poussée.

🖱️ **Depuis l’interface GitHub uniquement :**

- Cliquez sur **Code > Download ZIP** pour récupérer le projet si besoin, faites vos modifications,
  puis chargez-les via l’onglet **Pull requests > New pull request** en choisissant « compare across forks »
  et votre nouvelle branche téléchargée/chargée.
- Ou bien utilisez l’éditeur web GitHub : créez un fichier ou modifiez-en un depuis l’interface, puis, au moment
  d’enregistrer, GitHub vous proposera automatiquement de créer une nouvelle branche et la PR correspondante.

