# Google Hub pour GNOME

[![CI](https://github.com/maximeallanic/gnome-google-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/maximeallanic/gnome-google-hub/actions/workflows/ci.yml)
[![Licence : MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)
[![GNOME Shell 50 | 51](https://img.shields.io/badge/GNOME%20Shell-50%20%7C%2051-4a86cf.svg)](docs/installation.md#requirements)

[English](README.md) | Français

Google dans le bureau GNOME plutôt que dans des onglets : la recherche et les suggestions Google dans la recherche de
GNOME, Gemini dans un volet à un raccourci, une dictée vocale qui tourne sur votre ordinateur, et votre Agenda et vos
Tâches Google là où vous regardez déjà l'heure.

<p align="center">
  <img src="screenshots/search-typing.gif" width="880" alt="Saisie de « gtk docs » dans la recherche de GNOME : suggestions Google, Demander à Gemini et une page de l'historique du navigateur apparaissent au fil de la frappe">
</p>

## Fonctions

- **Google dans la recherche de GNOME.** Appuyez sur Super et tapez : « Rechercher sur Google », « Demander à
  Gemini », suggestions Google, adresses directes, favoris et historique de Chrome ou Chromium, événements et tâches.
- **Recherches par mot-clé.** `yt`, `maps`, `w` (Wikipédia dans votre langue), `gh`, `drive`, et les vôtres.
- **Créer une tâche en tapant.** `t Appeler le plombier demain` crée une tâche Google pour demain ; les dates sont
  lues dans votre langue.
- **Volet Gemini.** Super+G fait glisser la vraie application web Gemini depuis le bord droit, déjà chargée, et la
  cache quand vous cliquez ailleurs. Elle n'apparaît ni dans Alt+Tab ni dans la vue d'ensemble.
- **Voix locale.** Super+Maj+G : parlez, la phrase part vers Gemini. La transcription se fait sur votre ordinateur
  avec [whisper.cpp](https://github.com/ggml-org/whisper.cpp) ; le bouton micro de Gemini l'utilise aussi.
- **Tâches dans le menu de l'horloge.** En retard, aujourd'hui et les 7 prochains jours ; cocher pour terminer,
  ajouter, fonctionne hors ligne, et un résumé chaque matin.
- **Aucune clé d'API.** L'Agenda et les Tâches passent par le compte Google des Comptes en ligne de GNOME.
- **Votre langue.** Suit la langue de la session ; interface en anglais et en français, dates et dictée dans toutes
  les langues que connaissent les bibliothèques utilisées.

<table>
  <tr>
    <td><img src="screenshots/search.png" width="440" alt="Recherche de « gnome » : applications, groupe Google avec suggestions et groupe Chrome avec favoris"></td>
    <td><img src="screenshots/clock-menu-tasks.fr.png" width="360" alt="Menu de l'horloge avec une section Tâches : en retard, aujourd'hui, 7 prochains jours et un champ Ajouter une tâche"></td>
  </tr>
  <tr>
    <td><img src="screenshots/search-add-task.fr.png" width="440" alt="La saisie de « t Appeler le plombier demain » propose « Créer la tâche : Appeler le plombier », échéance mercredi"><br><img src="screenshots/search-calendar.png" width="440" alt="La recherche de « meeting » trouve l'événement Team meeting"><br><img src="screenshots/voice-pill.png" width="440" alt="La pastille d'écoute en haut de l'écran"></td>
    <td><img src="screenshots/gemini-drawer.png" width="300" alt="Le volet Gemini au bord droit de l'écran, déconnecté, sur la page de consentement de Google"></td>
  </tr>
</table>

<sub>Captures réelles dans un GNOME Shell imbriqué avec des données inventées (titres des tâches en anglais) ; le volet
est montré déconnecté. Leur fabrication : [screenshots/README.md](screenshots/README.md).</sub>

## Prérequis

- GNOME Shell 50 ou 51 (Wayland)
- Debian testing, Ubuntu, Fedora ou Arch (l'installateur installe les paquets) ; les autres distributions
  fonctionnent avec les [dépendances](docs/installation.md#dependencies) installées à la main
- Facultatif : un compte Google dans Paramètres > Comptes en ligne (Agenda et Tâches), `whisper-server` et environ
  470 Mo pour le modèle de reconnaissance vocale (dictée)

## Installation

Depuis un terminal de votre session GNOME, avec votre utilisateur habituel :

```sh
curl -fsSL https://raw.githubusercontent.com/maximeallanic/gnome-google-hub/main/install.sh | bash
```

L'installateur affiche ce qui manque et demande avant d'installer des paquets avec `sudo` et avant de télécharger le
modèle vocal, installe tout dans votre dossier personnel et termine par une vérification. Ensuite :

1. Fermez la session puis rouvrez-la.
2. Paramètres > Comptes en ligne > Google, avec Agenda activé.
3. Appuyez sur Super+G et connectez-vous une fois à Gemini.

Depuis un clone : `git clone https://github.com/maximeallanic/gnome-google-hub && cd gnome-google-hub && ./install.sh`
(`--help` pour les options). Détails, paquets par distribution et compilation de whisper.cpp :
[docs/installation.md](docs/installation.md) (en anglais).

Vérifier ou désinstaller à tout moment :

```sh
~/.local/share/google-hub/source/verify.sh
~/.local/share/google-hub/source/uninstall.sh     # --purge retire aussi réglages, modèle et connexion Gemini
```

## Utilisation

| Geste | Effet |
|---|---|
| Super, puis taper | Résultats Google, Chrome et Agenda & Tâches sous les applications |
| `yt …`, `maps …`, `w …`, `gh …`, `drive …` | Recherche directe sur ce site |
| `t Acheter du pain vendredi` | Une tâche Google pour vendredi |
| `demain`, `lundi`… | Les événements de ce jour |
| Super+G, ou l'icône étincelle | Ouvrir ou fermer le volet Gemini |
| Super+Maj+G | Demander à Gemini à la voix (de nouveau ou clic : terminer ; Échap : annuler) |
| Menu de l'horloge | Vos tâches ; cocher pour terminer, « + Ajouter une tâche » |

Plus de détails : [docs/usage.md](docs/usage.md).

## Configuration

Les raccourcis et la largeur du volet sont des clés GSettings, le démon lit `~/.config/google-hub/config.json`
(modèle et langue de la dictée, heure du résumé quotidien, profil du navigateur, langues de dates supplémentaires) et
`~/.config/google-hub/keywords.json` ajoute des mots-clés de recherche. Voir
[docs/configuration.md](docs/configuration.md).

## Confidentialité

Ce que vous tapez dans la recherche est envoyé au service de suggestions de Google ; l'Agenda et les Tâches parlent
aux API Google avec votre compte ; le volet est Gemini. Votre voix, votre historique de navigation et vos identifiants
restent sur votre ordinateur. Aucune télémétrie. Détails : [docs/privacy.md](docs/privacy.md).

## Dépannage et FAQ

`verify.sh` nomme la plupart des problèmes et leur solution. Voir [docs/troubleshooting.md](docs/troubleshooting.md)
et [docs/faq.md](docs/faq.md). Quelques réponses :

- **Est-ce fait par Google ?** Non, c'est un projet indépendant ([NOTICE](NOTICE.md)).
- **Faut-il une clé d'API ?** Non.
- **Fedora ?** Tout fonctionne, mais Fedora n'a pas de paquet `whisper-server` : la dictée demande de compiler
  whisper.cpp une fois ([comment](docs/installation.md#dictation-without-a-whisper-server-package)).
- **extensions.gnome.org ?** Pas encore : l'extension a besoin de son démon et de son volet, que l'installateur met
  en place.
- **Gemini a changé et « Demander » ne tape plus la question ?** Ouvrez un ticket ; les sélecteurs de la page sont
  dans `panel/google_hub_panel/selectors.js`.

## Documentation

La documentation détaillée est en anglais : [Installation](docs/installation.md) · [Utilisation](docs/usage.md) ·
[Configuration](docs/configuration.md) · [Dépannage](docs/troubleshooting.md) · [Confidentialité](docs/privacy.md) ·
[FAQ](docs/faq.md) · [Architecture](docs/architecture.md) · [Développement](docs/development.md) ·
[Journal des versions](CHANGELOG.md)

## Contribuer

Rapports de bogues, essais sur d'autres distributions et traductions sont bienvenus : voir
[CONTRIBUTING.md](CONTRIBUTING.md), [SUPPORT.md](SUPPORT.md) et le [code de conduite](CODE_OF_CONDUCT.md). Problèmes
de sécurité : [SECURITY.md](SECURITY.md).

## Licence

[MIT](LICENSE) © 2026 Maxime Allanic. Google, Gemini et les autres noms de produits Google sont des marques de
Google LLC ; ce projet n'est pas affilié à Google. Mentions des tiers : [NOTICE.md](NOTICE.md).
