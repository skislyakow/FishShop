#!/usr/bin/env node
// Кроссплатформенный бутстрап окружения FishShop.
//
// Ставит личный инструментарий (skills) и зависимости обоих стеков:
//   - skills  → .agents/skills  (из skills-lock.json; в git не хранятся)
//   - cms     → node_modules    (npm ci)
//   - bot     → .venv           (uv sync, когда появится bot/)
//
// Использование:
//   npm run setup          # dev-машина
//   npm run setup:prod     # сервер/CI: без skills
//   node scripts/bootstrap.mjs --help
//   node scripts/bootstrap.mjs --no-skills --no-cms --no-bot
//
// Подробности: docs/SETUP.md

import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const argv = new Set(process.argv.slice(2));

if (argv.has('--help') || argv.has('-h')) {
  printHelp();
  process.exit(0);
}

const opts = {
  skills: !argv.has('--no-skills'),
  cms: !argv.has('--no-cms'),
  bot: !argv.has('--no-bot'),
};

const SKILLS_DIR = join(ROOT, '.agents', 'skills');
const CMS_DIR = join(ROOT, 'cms');
const BOT_DIR = join(ROOT, 'bot');

console.log('FishShop: развёртывание окружения');
console.log(`  каталог: ${ROOT}`);

checkNodeVersion();

let failed = false;
if (opts.skills) failed = !runSkills() || failed;
if (opts.cms) failed = !runCms() || failed;
if (opts.bot) failed = !runBot() || failed;

console.log('');
if (failed) {
  console.error('⚠ Часть шагов завершилась с ошибкой — смотри вывод выше.');
  process.exit(1);
}
console.log('✔ Окружение готово. Strapi запускается командой: cd cms && npm run develop');

// ---------------------------------------------------------------------------

function printHelp() {
  console.log(`FishShop bootstrap

Usage: node scripts/bootstrap.mjs [options]

Options:
  --no-skills   не восстанавливать skills (.agents/skills)
  --no-cms      не ставить зависимости Strapi
  --no-bot      не ставить зависимости Python-бота
  -h, --help    показать эту справку

Запускай флаги напрямую через node: npm перехватывает свои флаги вида --no-*.
Готовый npm-скрипт без skills: npm run setup:prod`);
}

function checkNodeVersion() {
  const major = Number(process.versions.node.split('.')[0]);
  if (major < 20 || major > 26) {
    console.warn(`⚠ Node ${process.versions.node}: Strapi 5 ожидает Node 20–26 (см. docs/SETUP.md).`);
  }
}

/** Запускает команду в shell (кроссплатформенно резолвит npm/npx/uv). */
function run(cmd, cwd = ROOT) {
  console.log(`\n$ ${cmd}`);
  const res = spawnSync(cmd, { cwd, stdio: 'inherit', shell: true });
  if (res.error) {
    console.error(`✖ Не удалось запустить: ${cmd}\n  ${res.error.message}`);
    return false;
  }
  if (res.status !== 0) {
    console.error(`✖ Команда завершилась с кодом ${res.status}: ${cmd}`);
    return false;
  }
  return true;
}

function commandExists(cmd) {
  const res = spawnSync(`${cmd} --version`, { stdio: 'ignore', shell: true });
  return !res.error && res.status === 0;
}

function isNonEmptyDir(dir) {
  try {
    return existsSync(dir) && readdirSync(dir).length > 0;
  } catch {
    return false;
  }
}

function runSkills() {
  console.log('\n— skills');
  if (isNonEmptyDir(SKILLS_DIR)) {
    console.log('  уже установлены — пропускаю (.agents/skills не пуст).');
    return true;
  }
  return run('npx -y skills@latest experimental_install');
}

function runCms() {
  console.log('\n— cms (Strapi)');
  const env = join(CMS_DIR, '.env');
  const envExample = join(CMS_DIR, '.env.example');
  if (!existsSync(env) && existsSync(envExample)) {
    copyFileSync(envExample, env);
    console.log('  создан cms/.env из cms/.env.example — заполни секреты (docs/SETUP.md).');
  }
  const cmd = existsSync(join(CMS_DIR, 'package-lock.json')) ? 'npm ci' : 'npm install';
  return run(cmd, CMS_DIR);
}

function runBot() {
  console.log('\n— bot (Python)');
  if (!existsSync(join(BOT_DIR, 'pyproject.toml'))) {
    console.log('  bot/ ещё нет — пропускаю (появится на этапе Telegram-бота).');
    return true;
  }
  if (!commandExists('uv')) {
    console.error('  ✖ не найден uv. Установка: https://docs.astral.sh/uv/getting-started/installation/');
    return false;
  }
  return run('uv sync --project bot');
}
