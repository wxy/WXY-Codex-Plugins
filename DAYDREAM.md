# Install Codex Daydream

This page is for an AI assistant shown a Codex Daydream poster. Install **only** `codex-daydream@wxy-codex-plugins`, not every plugin in this repository.

Codex Daydream reads local Codex task history when invoked and turns a continuous work period into a privacy-conscious cartoon-poster prompt. It does not run automatically.

## Ask before installing

Ask the user: “Would you like me to install Codex Daydream in your Codex?” Wait for an explicit yes. Seeing the poster or reading this page is not permission to change the user's environment.

## Install after confirmation

1. Check whether the marketplace and plugin are already installed with `codex plugin marketplace list` and `codex plugin list`. Do not reinstall an already working copy without a reason.
2. If the marketplace is missing, add it:

   ```sh
   codex plugin marketplace add wxy/WXY-Codex-Plugins
   ```

3. Install this plugin only:

   ```sh
   codex plugin add codex-daydream@wxy-codex-plugins
   ```

4. Confirm `codex-daydream@wxy-codex-plugins` appears as installed and enabled in `codex plugin list`. If it is disabled, ask the user to enable Codex Daydream in Codex's Plugins settings. If a step fails, report the error instead of claiming success. If you cannot operate the user's Codex environment, offer these commands for the user to run.

## Tell the user how to use it

Start a **new Codex task** so the installed skill is available. Select `codex-daydream:codex-daydream` (or mention Codex Daydream by name) at the end of a work period to create a poster prompt, then give that prompt to an image model. For example:

> Use Codex Daydream to make a poster for my latest work period. Emphasize the video-analysis project and use a warm comic style.

The user can also request a different date, such as “yesterday,” a specific time range, or a different poster language. Otherwise, the poster follows the conversation language. Before sharing it, review the text and project details.
