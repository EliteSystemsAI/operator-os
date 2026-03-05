module.exports = {
  apps: [
    {
      name: 'elite-worker',
      script: '/Users/eliteserver/operatoros/.venv/bin/python3',
      args: 'ops/claude_worker.py',
      cwd: '/Users/eliteserver/operatoros',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      max_restarts: 20,
      restart_delay: 10000,
      env: {
        PYTHONPATH: '/Users/eliteserver/operatoros',
      },
      out_file: '/Users/eliteserver/.pm2/logs/elite-worker-out.log',
      error_file: '/Users/eliteserver/.pm2/logs/elite-worker-error.log',
    },
    {
      name: 'elite-analyst',
      script: '/Users/eliteserver/operatoros/.venv/bin/python3',
      args: 'ops/analyst.py',
      cwd: '/Users/eliteserver/operatoros',
      interpreter: 'none',
      autorestart: false,
      watch: false,
      cron_restart: '0 */2 * * *',
      env: {
        PYTHONPATH: '/Users/eliteserver/operatoros',
      },
      out_file: '/Users/eliteserver/.pm2/logs/elite-analyst-out.log',
      error_file: '/Users/eliteserver/.pm2/logs/elite-analyst-error.log',
    },
    {
      name: 'elite-meta-monitor',
      script: '/Users/eliteserver/operatoros/.venv/bin/python3',
      args: 'ops/meta_monitor.py',
      cwd: '/Users/eliteserver/operatoros',
      interpreter: 'none',
      autorestart: false,
      watch: false,
      cron_restart: '0 * * * *',
      env: {
        PYTHONPATH: '/Users/eliteserver/operatoros',
      },
      out_file: '/Users/eliteserver/.pm2/logs/elite-meta-monitor-out.log',
      error_file: '/Users/eliteserver/.pm2/logs/elite-meta-monitor-error.log',
    },
    {
      name: 'elite-watchdog',
      script: '/Users/eliteserver/operatoros/.venv/bin/python3',
      args: 'ops/watchdog.py',
      cwd: '/Users/eliteserver/operatoros',
      interpreter: 'none',
      autorestart: false,
      watch: false,
      cron_restart: '*/15 * * * *',
      env: {
        PYTHONPATH: '/Users/eliteserver/operatoros',
      },
      out_file: '/Users/eliteserver/.pm2/logs/elite-watchdog-out.log',
      error_file: '/Users/eliteserver/.pm2/logs/elite-watchdog-error.log',
    },
    {
      name: 'elite-analyst-night',
      script: '/Users/eliteserver/operatoros/.venv/bin/python3',
      args: 'ops/analyst.py --night',
      cwd: '/Users/eliteserver/operatoros',
      interpreter: 'none',
      autorestart: false,
      watch: false,
      cron_restart: '0 13 * * *',
      env: {
        PYTHONPATH: '/Users/eliteserver/operatoros',
      },
      out_file: '/Users/eliteserver/.pm2/logs/elite-analyst-night-out.log',
      error_file: '/Users/eliteserver/.pm2/logs/elite-analyst-night-error.log',
    },

    // Content Intelligence — runs daily at 6am AEST (8pm UTC previous day)
    {
      name: 'elite-content-intel',
      script: '/Users/eliteserver/operatoros/.venv/bin/python3',
      args: 'ops/content_intelligence.py',
      cwd: '/Users/eliteserver/operatoros',
      interpreter: 'none',
      autorestart: false,
      watch: false,
      cron_restart: '0 20 * * *',  // 8pm UTC = 6am AEST
      env: {
        PYTHONPATH: '/Users/eliteserver/operatoros',
      },
      out_file: '/Users/eliteserver/.pm2/logs/elite-content-intel-out.log',
      error_file: '/Users/eliteserver/.pm2/logs/elite-content-intel-error.log',
    },

    // Instagram Analytics — runs daily at 7am AEST (9pm UTC previous day)
    {
      name: 'elite-ig-analytics',
      script: '/Users/eliteserver/operatoros/.venv/bin/python3',
      args: 'ops/instagram_analytics.py',
      cwd: '/Users/eliteserver/operatoros',
      interpreter: 'none',
      autorestart: false,
      watch: false,
      cron_restart: '0 21 * * *',  // 9pm UTC = 7am AEST
      env: {
        PYTHONPATH: '/Users/eliteserver/operatoros',
      },
      out_file: '/Users/eliteserver/.pm2/logs/elite-ig-analytics-out.log',
      error_file: '/Users/eliteserver/.pm2/logs/elite-ig-analytics-error.log',
    },

    // Content Autopilot — generates 5 drafts daily at 7am AEST (9pm UTC previous day)
    {
      name: 'elite-content-autopilot',
      script: '/Users/eliteserver/operatoros/.venv/bin/python3',
      args: 'ops/content_autopilot.py',
      cwd: '/Users/eliteserver/operatoros',
      interpreter: 'none',
      autorestart: false,
      watch: false,
      cron_restart: '0 21 * * *',  // 9pm UTC = 7am AEST
      env: {
        PYTHONPATH: '/Users/eliteserver/operatoros',
      },
      out_file: '/Users/eliteserver/.pm2/logs/elite-content-autopilot-out.log',
      error_file: '/Users/eliteserver/.pm2/logs/elite-content-autopilot-error.log',
    },

    // CommandOS — Telegram AI Command Bot (always-on)
    {
      name: 'elite-command-bot',
      script: '/Users/eliteserver/operatoros/.venv/bin/python3',
      args: '-m apps.command.main',
      cwd: '/Users/eliteserver/operatoros',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      max_restarts: 20,
      restart_delay: 5000,
      env: {
        PYTHONPATH: '/Users/eliteserver/operatoros',
      },
      out_file: '/Users/eliteserver/.pm2/logs/elite-command-bot-out.log',
      error_file: '/Users/eliteserver/.pm2/logs/elite-command-bot-error.log',
    },
  ]
}
