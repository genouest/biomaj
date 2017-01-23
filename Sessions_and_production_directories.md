---
title: Directories
layout: default
---

# Sessions

Each run creates or uses a session. The session holds the status of the update/delete/... as well as other specific action information (list of files downloaded, release, ...).

If the previous session is successful, the next run will create a new session.
If previous session failed (error during download, wrong configuration, ...), the next run will reload previous session and restart actions from the failed step.

Example:

Run 1:
 init OK => .. => download KO stop here

Run 2:

 init SKIP => ... => download OK => postprocess OK => ...


# Production directories

When a bank is successfully updated, the Bank adds a new *production* directory with a release name.
Each production maps to a session.

# Publish

One and only one bank release can be published for each bank. A *published* bank creates a symbolic link **current** on the specified released. This helps user accessing a bank with the same path (/../mybank/current). You can manage publishing at update time or later on with the --publish or --publish-version options.
