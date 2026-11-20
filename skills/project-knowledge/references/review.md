# Reviewing one topic

A map says what the product does. A review goes through the same product again with one topic in mind (is it safe, is its API in order, is its UI consistent) and a fixed list of questions, so that nothing is skipped because it looked fine. It is a separate pass that a person asks for by name. It opens every entry point in its scope again, so it costs about as much reading as the features it covers; do one topic per pass.

A review leaves three things:

- **Rules the pages were missing.** What the code answers plainly (only an admin may open this, a file may be 10 MB at most) is a numbered rule on the feature's page, like any other rule.
- **Gaps.** Each doubt is one gap with `topic` set, in the same queue as every other gap.
- **A run page** that says which features were reviewed and which were not, so the pass can be continued.

It never changes application code and never decides a gap.

## What a review is not

A review reads code. It runs no scanner, no test and no application, like every other pass of this skill.

- Known vulnerabilities in dependencies, outdated packages, secrets in the Git history and a misconfigured server are found by tools, not by reading. Name the tool under "Not covered" in the report (`npm audit`, `pip-audit`, `osv-scanner`, a secret scanner). Run one only when the person asks.
- It is not a penetration test and not a certificate. "No gaps found" means the questions below found nothing in the code that was read. Say it that way, never "the product is secure".

## The pass

1. **Scope.** The whole product, an area, one feature, or what changed since a commit or a day ("review the security of what changed last week" takes the features the diff touches). Say which before you start.
2. **The list.** A review needs a map: [the inventory file](../SKILL.md#the-inventory-file) is its list of features and entry points. Without a vault, say so and offer a map first. A question about one feature in a repository that has no vault is an **investigate**, and it ends as a report. A feature the inventory has as `not started` is reviewed from the code alone, and the run page says its page does not exist yet.
3. **The run page.** Create `runs/<date>-review-<topic>.md` with `status: "partial"`: the topic, the scope, the revision, and the features in scope as a checklist. Tick a feature when every question was asked of every one of its entry points. Save it after each feature. A later session reads this page first and goes on with the first unticked feature.
4. **One feature at a time.** Read the feature's page, then open each entry point and answer the topic's questions from the code. The page tells you where to look; it is not the evidence. Ask every question of every entry point it applies to, and do not stop at the first finding.
5. **Each answer goes to one place.**
   - The code does it, and the page does not say so: add the rule to the page, with the next free number. For security, also set [the page's `access`](format.md#properties).
   - The code does it, and the page says so: nothing to write.
   - The code does not do it, does it in one place and not in another, or you cannot tell whether it is meant: a gap.
6. **Finish.** Run `check`. Set the run page to `current` when every feature in scope is ticked. Report real counts: features reviewed out of those in scope, rules added, gaps written by priority, and "Not covered" with the tools that would cover it.

## Writing the gaps

The rules in [gaps.md](gaps.md) apply. A review adds these:

- **Look in the queue first.** A gap that already asks the question gets `topic` when it has none and a dated line in `Discussion`; it does not get a twin.
- **One doubt per page.** The same missing check in several entry points of one feature is one gap that lists them. In two features it is two gaps, because each feature has its own owner and decision.
- **The title is the question a person decides**: "Should a member be able to change another member's role by saving the profile form?", not "Broken access control in users.save".
- **`kind` as usual**: `product-gap` when a rule the product enforces elsewhere is not enforced here, `conflict` when two places disagree (the web refuses what the server accepts), `knowledge-gap` when you cannot tell whether it is meant, `product-plan` for something to add (a limit on sign-in attempts).
- **`priority`**: `high` when a person can read or change what is not theirs, act without signing in, or move money; `medium` when it needs a signed-in insider or an unusual condition; `low` otherwise.
- **Evidence says how it is reached, in words**: which entry point, which check is absent, which symbol. `NOT RUN` for what was only read. No working request, script or payload: the page is for the person who fixes it.
- **A security gap describes a weakness of a live product.** Before the vault is published where people outside the team can read it, tell the person these pages are in it.

## Security

Ask these of every entry point.

1. **Who can reach it?** Nobody signed in, anyone signed in, one role? Find the check on the server. A menu that hides the link and a redirect in the client are not a check.
2. **Whose record is it?** When the request carries an id, does the server check that the record belongs to the caller, their team or their tenant? Is every list filtered by the caller on the server?
3. **What may be changed?** Which fields does it accept? Can the caller set one they must not: role, owner, tenant, price, balance, status, a "verified" flag? Look for a request body passed whole into an update.
4. **What comes back?** Fields the caller should not see: password hashes, tokens, other people's contact details, internal notes. Does an error tell whether an account or a record exists?
5. **What is done with the input?** Is raw input put into a query, a shell command, a file path, HTML shown to other people, a URL the server fetches, or a redirect target? Are size and count limited?
6. **Files.** Are type and size checked on the server? Where are uploads kept, who can fetch them, can a name be guessed?
7. **Signing in and recovery.** Is the number of attempts limited for sign-in, reset, invite and code entry? How long does a reset, invite or sign-in link live, and does it work twice? What ends a session: a password change, a removed role?
8. **Secrets.** A key in client code or in the repository, a secret written to a log, a token in a URL.

And by kind of entry point:

9. **What another system calls.** Is the sender proven (a signature, a shared secret)? Can the same call be replayed?
10. **What runs on its own.** With whose rights does the job act? Does it cross tenants? Does it trust records that users control?
11. **What the product sends out.** Is the address taken from the request? Does the message carry another person's data, or a link with a token?
12. **Money and what cannot be undone.** Does the amount come from the client? Is a repeated request safe? Is there a confirmation?

## API

For what another system can call, and for the calls the product makes.

1. **Who calls it?** Search every client in the repository, the tests and the documentation. An endpoint nothing calls is a gap ("Is it still needed?"), unless the API is public for outside callers; then say where it is documented.
2. **The reverse.** A client that calls something the server does not have, sends a field the server ignores, or reads a field the server does not return.
3. **Two ways to do one thing.** An old and a new version of the same call. Which do the clients use, and is the old one marked?
4. **Marked as outdated and still used.** A procedure the code marks deprecated (a comment, an annotation, a `legacy` or `v1` name) that a client still calls, and calls to another service that the code or its SDK marks deprecated. Outdated package versions are for a tool; see "What a review is not".
5. **Input.** Does every endpoint check its input on the server? Do lists have a maximum page size?
6. **Consistency.** The same thing under two names, errors of different shape or status, dates or money in different formats between endpoints.
7. **The written contract.** An OpenAPI file, a README or types shared with clients that say something else than the code is a `conflict` gap.
8. **Calls out.** Is there a timeout and a retry? What does the person see when the other service is down? Is the call safe to repeat?

## UI

For every screen, in every client.

1. **States.** What does a person see while it loads, when the list is empty, when the request fails, when they have no permission, when the record does not exist? A state the screen does not handle is a gap.
2. **The same thing built twice.** Go through the component folders and list each control that exists more than once: two date pickers, three confirm dialogs, two ways to show an error. Copies that look or behave differently are a gap that names the screens. Copies that are the same are one `low` gap per control, as a proposal to keep one.
3. **Words.** One action or thing under different names on different screens, one refusal with different messages, text written in one language where the product is translated.
4. **Actions.** Something that cannot be undone and asks no confirmation, a button that stays active while its request runs, input lost without a warning when the person leaves.
5. **Shown and allowed.** A control shown to a person whose request the server refuses, or hidden from one the server would allow.
6. **Forms.** A check in the client that differs from the server's. An error shown only as a general message when it belongs to one field.
7. **Clients.** What one client has and another lacks; this also goes into "Where the apps differ" on the feature's page.
8. **Basics for everyone.** A field without a label, a button with an icon and no name, information given by colour alone. Read from the code; this is not an accessibility audit.

## Another topic

A person may name a topic that has no list here: data, performance, texts, "are there duplicate components". Write five to ten questions for it, show them to the person, and run the same pass with them. `topic` on the gaps is the nearest of the six values in [gaps.md](gaps.md).
