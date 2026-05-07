# Bolgheri Daily Brief — Architecture

P3 #13 として 2026-05-07 fix 後の最新アーキテクチャを Mermaid 形式で可視化。

最終更新: 2026-05-07

---

## 1. システム全体像

```mermaid
flowchart TB
    classDef external fill:#FBF5EA,stroke:#9E5E42,color:#241811
    classDef gh fill:#0A1E3F,stroke:#0A1E3F,color:#fff
    classDef storage fill:#E8DDC9,stroke:#5D4232,color:#241811
    classDef user fill:#C17F5E,stroke:#9E5E42,color:#fff

    subgraph ext[External Services]
        gmail[Gmail<br/>9 source newsletters]:::external
        gemini[Google Gemini API<br/>gemini-2.5-flash]:::external
        groq[Groq API<br/>llama-3.3-70b]:::external
        ghmodels[GitHub Models<br/>gpt-4.1]:::external
        polly[Pollinations.ai<br/>Hero image gen]:::external
    end

    subgraph gha[GitHub Actions Cron]
        cron[Schedule: 21:00 UTC<br/>= 06:00 JST]:::gh
        daily[Daily Translation<br/>matrix max-parallel=3]:::gh
        backfill[Batch Backfill]:::gh
        deploy[Deploy Next.js<br/>workflow_run trigger]:::gh
        lint[Lint<br/>actionlint + py syntax]:::gh
    end

    subgraph repo[GitHub Repo: TH1214/newsletter-dashboard]
        content[content/&lt;source&gt;/&lt;date&gt;.md<br/>真実の源]:::storage
        images[static/images/&lt;source&gt;/&lt;date&gt;.png]:::storage
        issues[GitHub Issues<br/>auto-generated on failure]:::storage
    end

    subgraph publish[Publishing]
        nextjs[Next.js 14 build<br/>9 sources × 30+ days]:::gh
        pages[GitHub Pages CDN]:::storage
    end

    user[User<br/>th1214.github.io/newsletter-dashboard/]:::user

    cron --> daily
    daily -.fetch.-> gmail
    daily -.translate primary.-> gemini
    daily -.fallback 1.-> groq
    daily -.fallback 2.-> ghmodels
    daily -.hero img.-> polly
    daily -->|commit| content
    daily -->|commit| images
    daily -.failure 0 articles.-> issues

    backfill -.same chain.-> gemini
    backfill --> content

    daily -->|workflow_run| deploy
    backfill -->|workflow_run| deploy
    content --> deploy
    images --> deploy
    deploy --> nextjs
    nextjs --> pages
    pages --> user

    lint -.PR check.-> daily
    lint -.PR check.-> backfill
    lint -.PR check.-> deploy
```

## 2. Translation pipeline (single source detail)

```mermaid
sequenceDiagram
    autonumber
    participant Cron as GitHub Cron<br/>21:00 UTC
    participant Matrix as Matrix Job<br/>(per source)
    participant Fetch as fetch_gmail.py
    participant Gmail as Gmail API
    participant Trans as translate_gemini.py
    participant Gemini as Gemini API
    participant Groq as Groq API
    participant GH as GitHub Models
    participant Hero as generate_hero_image.py
    participant Aggr as Aggregator Job

    Cron->>Matrix: Spawn 9 parallel jobs (max 3 concurrent)
    Matrix->>Fetch: source + target_date
    Fetch->>Gmail: search after:-12h before:+27h
    Gmail-->>Fetch: latest matching email

    alt NO_EMAIL_FOUND
        Fetch-->>Matrix: status=SKIPPED_NO_EMAIL
    else email found
        Fetch-->>Matrix: email body
        Matrix->>Trans: stdin=email body
        
        Trans->>Gemini: chunk-by-chunk translation
        alt Gemini OK
            Gemini-->>Trans: translated chunks
        else Gemini fails (HTTP 503/429/etc)
            Note over Trans: BackendError raised<br/>fallback to Groq
            Trans->>Groq: same prompts
            alt Groq OK
                Groq-->>Trans: translated chunks
            else Groq fails
                Trans->>GH: same prompts
                GH-->>Trans: translated chunks
            end
        end
        
        Trans-->>Matrix: combined .md output
        Matrix->>Hero: generate hero image
        Hero-->>Matrix: PNG (non-blocking)
        Matrix-->>Aggr: artifact (content + image)
    end

    Aggr->>Aggr: Apply all artifacts<br/>commit + push
    alt translated count == 0 AND failed > 0
        Aggr-->>Aggr: Create GitHub Issue<br/>(P0 #2 alert)
    end
    Aggr->>Aggr: Trigger deploy.yml<br/>(workflow_run + gh workflow run)
```

## 3. Reliability features (2026-05-07 後の状態)

```mermaid
mindmap
  root((Reliability))
    Translation
      Triple-backend fallback chain
        Gemini → Groq → GitHub Models
        BackendError exception-based
      Per-chunk retry with backoff
        15s / 30s / 60s exponential
        Max 3 retries per chunk
      Rate-limit aware
        max-parallel=3 in matrix
        7s sleep between chunks
    Idempotency
      Skip-if-exists with integrity check
        front matter required
        body size > 500 bytes
      Re-translate on corrupt files
    Observability
      Per-source status output
        TRANSLATED / SKIPPED_* / FAILED_*
      Aggregator summary in workflow log
      /status/ page on production
        14-day delivery heatmap
        Per-source last delivery
        7-day success rate
    Alerting
      Auto Issue on critical failure
        translated == 0 AND failed > 0
        Includes runbook link
      Workflow failure email
        GitHub default notification
    Deploy
      workflow_run trigger
        PAT-free auto deploy
        conclusion=success guard
      push paths trigger
        for manual edits
      workflow_dispatch
        manual override
```

## 4. Date window logic (P0 #1 fix - 2026-05-07)

```mermaid
gantt
    title fetch_gmail.py date_override window evolution
    dateFormat HH:mm
    axisFormat %H:%M
    
    section Old (before fix)
    Window for 2026-05-07 :crit, old, 00:00, 27h
    
    section New (-12h expansion)
    Window for 2026-05-07 :active, new, -12h, 39h
    
    section Email arrivals (UTC, sample)
    WSJ 10:09 UTC :milestone, 10:09, 0min
    DealBook 11:51 UTC :milestone, 11:51, 0min
    Skift 11:45 UTC :milestone, 11:45, 0min
    Short Squeez 08:31 UTC :milestone, 08:31, 0min
```

注釈: 5/6 の典型的配信時刻 (UTC) は 08:00〜16:00。旧ウィンドウ (5/7 00:00 JST = 5/6 15:00 UTC 以降) では先頭の 5/6 朝着メールを取り逃がしていた。新ウィンドウ (5/6 12:00 JST = 5/6 03:00 UTC 以降) で完全カバー。

## 5. ファイルマップ (主要)

```mermaid
graph LR
    classDef wf fill:#FBF5EA,stroke:#9E5E42
    classDef py fill:#E8DDC9,stroke:#5D4232
    classDef next fill:#0A1E3F,stroke:#0A1E3F,color:#fff
    classDef doc fill:#C17F5E,stroke:#9E5E42,color:#fff

    daily[.github/workflows/daily-translate.yml]:::wf
    backfill[.github/workflows/batch-backfill.yml]:::wf
    deploy[.github/workflows/deploy.yml]:::wf
    lint[.github/workflows/lint.yml]:::wf

    fetch[scripts/fetch_gmail.py]:::py
    trans[scripts/translate_gemini.py]:::py
    prompt[scripts/translate_prompt.md]:::py
    hero[scripts/generate_hero_image.py]:::py

    nlib[v2-next/lib/content.ts]:::next
    nstatus[v2-next/app/status/page.tsx]:::next
    nlayout[v2-next/app/layout.tsx]:::next

    runbook[RUNBOOK.md]:::doc
    arch[ARCHITECTURE.md]:::doc
    claude[CLAUDE.md]:::doc
    spec[Bolgheri_Daily_Brief_仕様書_v3.2_2026-05-07.docx]:::doc

    daily --> fetch
    daily --> trans
    daily --> hero
    backfill --> fetch
    backfill --> trans
    backfill --> hero

    trans --> prompt

    deploy --> nlib
    nlib --> nstatus

    lint --> trans
    lint --> daily
    lint --> deploy
```
