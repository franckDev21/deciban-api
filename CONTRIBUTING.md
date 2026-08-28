# Contribuer à Deciban

Les objections comptent plus que les compliments. Si vous trouvez une erreur que nous n'avons pas signalée nous-mêmes, elle nous intéresse davantage que n'importe quel encouragement.

---

## Ce dont le projet a le plus besoin

| Domaine | Pourquoi c'est ouvert |
|---|---|
| **Design d'interface** | Le terrain est large et peu occupé. Carte blanche : une proposition de direction artistique vit sous sa propre classe CSS sans toucher aux autres. |
| **Statistique** | Les poids du moteur sont plausibles, pas mesurés. Les calibrer est le cœur du sujet. |
| **Red team** | Essayez de tromper le système et documentez comment vous y arrivez. Une défense que personne n'a attaquée ne vaut rien. |
| **Frontend** | La mesure se fait dans le navigateur : geste, frappe, rythme. Travail fin sur les événements et le canvas. |
| **Backend et données** | FastAPI et SQLAlchemy, plus la partie estimation. |

Vous ne codez pas ? Tester, écrire de la documentation, ou discuter des règles a autant de valeur. Le débat sur ce qui est juste compte autant que le code.

---

## Mettre en route

```bash
git clone git@github.com:franckDev21/deciban-api.git
cd deciban-api
docker compose up --build
```

Docker évite d'installer les dépendances à la main et garantit le même environnement sous Windows, Linux et macOS. Les détails sont dans le [README](README.md).

Le projet vit dans deux dépôts. Pour faire tourner la pile complète, il faut aussi l'interface : [deciban-web](https://github.com/franckDev21/deciban-web).

---

## Le cycle d'une contribution

### 1. Ouvrez une issue avant d'écrire du code

Pour un correctif évident, allez-y directement. Pour tout le reste, une issue évite de découvrir après coup que deux personnes ont écrit la même chose, ou qu'une idée avait déjà été écartée pour une raison qui n'apparaît pas dans le code.

### 2. Créez une branche

```bash
git switch -c fix/intervalle-de-couverture
```

Nommez-la par ce qu'elle fait : `fix/`, `feat/`, `docs/`, `test/`, `refactor/`.

### 3. Écrivez le test avant le correctif quand c'est possible

Un test qui échoue prouve que le bug existe. Le même test qui passe prouve qu'il est corrigé. Sans lui, personne ne peut vérifier votre affirmation.

### 4. Vérifiez avant de proposer

```bash
.venv/bin/pytest && .venv/bin/ruff check deciban tests
```

L'intégration continue relancera tout, mais échouer en local coûte deux minutes là où échouer sur GitHub en coûte dix.

### 5. Rédigez le message de commit

Le format est `type(portée): ce que ça fait`, puis une ligne vide, puis **pourquoi**.

```
fix(couverture): quantile exact de la Bêta au lieu d'une gaussienne

Sur deux ou trois contrôles la loi est trop asymétrique pour qu'une
approximation normale tienne dans [0, 1] : il fallait l'écrêter, ce qui
était l'aveu du problème.
```

Le *quoi* se lit dans le diff. Le *pourquoi* ne se lit nulle part ailleurs, et c'est ce dont la personne qui relira dans six mois aura besoin.

### 6. Ouvrez la pull request

Décrivez ce qui change, ce que vous avez vérifié, et ce dont vous n'êtes pas sûr. **Cette dernière partie est la plus utile.** Une PR qui dit « je ne sais pas si ce seuil est le bon » obtient une meilleure relecture qu'une PR qui affirme.

---

## Ce que la relecture regarde

- **Les tests passent**, et un comportement nouveau est couvert
- **Le pourquoi est écrit**, dans le commit ou dans un commentaire
- **Aucune donnée sensible** n'est ajoutée : clés, jetons, base locale
- **Le contenu reste bilingue** : toute chaîne ajoutée existe en français et en anglais, sinon un test échoue
- **Aucune sur-promesse** : si un chiffre est estimé et non mesuré, le texte doit le dire

Ce dernier point n'est pas une formalité. La crédibilité du projet tient à ce qu'il annonce exactement ce qu'il fait.

---

## Trois règles sur lesquelles le projet ne bougera pas

**Le score appartient à la personne.** Il est visible et opposable par elle seule. Aucune fonctionnalité ne publiera le score d'un tiers, et aucun classement de suspects n'existera. Une PR qui va dans ce sens sera refusée quelle que soit sa qualité technique.

**Ne rien avoir ne coûte rien.** Absence de webcam, matériel ancien, saisie vocale, clavier adapté : la contribution est nulle, jamais négative. Un système qui exige du bon matériel punit ceux qui n'en ont pas.

**Le système peut s'abstenir.** En dessous d'un certain volume de preuve, il répond « données insuffisantes ». Y être n'est pas une accusation.

---

## Modifier le moteur

Les seuils vivent dans `deciban/services/`. Chacun est documenté sur la page `/algorithme`, avec le fichier où le trouver.

Si vous changez une valeur :

1. **Dites pourquoi.** Une mesure, un raisonnement, une attaque réussie.
2. **Mettez à jour `src/lib/algo-impl.ts` du dépôt deciban-web**, qui documente les seuils réels. Un décalage entre le code et la page est un bug.
3. **Ajoutez un test** qui capture le comportement voulu.

Les cinq paramètres les plus discutables sont listés en bas de la page `/algorithme`. C'est là qu'il faut taper en priorité.

---

## Signaler une faille de sécurité

N'ouvrez pas d'issue publique. Écrivez en privé au responsable du dépôt. Une faille dans un outil qui manipule de la biométrie comportementale mérite d'être corrigée avant d'être connue.

---

## Licence

En proposant une contribution, vous acceptez qu'elle soit distribuée sous licence MIT, comme le reste du projet.
