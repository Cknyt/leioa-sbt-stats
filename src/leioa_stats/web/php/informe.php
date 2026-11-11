<?php
// Informe privado del diario de visitas: lee datos/visitas-AAAA-MM.php (lo escribe
// registrar.php) y muestra los aparatos que entran y cada visita, una a una.
//
// Contraseña: la publicación crea informe-clave.php con la huella (hash) del secreto de GitHub
// INFORME_CLAVE. Aquí solo se compara con esa huella; la contraseña no está en el código. Sin
// ese archivo, el informe está desactivado. No usa cookies: la contraseña se pide cada vez.
//
// Compatible con PHP 7.4 o posterior (no se conoce la versión exacta del hosting).

declare(strict_types=1);

require_once __DIR__ . '/comun.php';

const ONLINE_GAP = 90;       // Activo en los últimos 90 segundos: "conectado ahora".
const MAX_VISITS = 150;      // Visitas que se muestran en el diario.

const DAYS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];

/** Lee las líneas de los archivos del diario (sin la primera, la protectora). */
function read_records(string $dir): array
{
    $records = [];
    foreach (glob("$dir/visitas-*.php") ?: [] as $file) {
        foreach (array_slice(file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES), 1) as $line) {
            $record = json_decode($line, true);
            if (is_array($record)) {
                $records[] = $record;
            }
        }
    }
    return $records;
}

/** Junta los avisos de cada página abierta: hora, página, aparato, segundos y secciones. */
function build_views(array $records): array
{
    $views = [];
    foreach ($records as $r) {
        if (($r['t'] ?? '') === 'start') {
            $views[$r['v']] = [
                'ts' => $r['ts'], 'last' => $r['ts'], 'page' => $r['p'], 'referrer' => $r['r'],
                'device' => device_key($r['ua'], $r['w']), 'ua' => $r['ua'], 'screen' => $r['w'],
                'seconds' => 0, 'sections' => [],
            ];
        }
    }
    foreach ($records as $r) {
        if (!isset($views[$r['v']])) {
            continue; // Aviso de una página cuyo inicio no se registró.
        }
        $view = &$views[$r['v']];
        $view['last'] = max($view['last'], $r['ts']);
        if ($r['t'] === 'ping') {
            $view['seconds'] = max($view['seconds'], $r['s']);
        } elseif ($r['t'] === 'section' && !in_array($r['id'], $view['sections'], true)) {
            $view['sections'][] = $r['id'];
        }
        unset($view);
    }
    usort($views, fn($a, $b) => $a['ts'] <=> $b['ts']);
    return $views;
}

/**
 * Agrupa las páginas en visitas: mismo aparato y menos de 30 minutos entre el final de una
 * página y el inicio de la siguiente. El tiempo de la visita es la suma del tiempo visible.
 */
function build_visits(array $views): array
{
    $visits = [];
    $open = []; // Última visita de cada aparato.
    foreach ($views as $view) {
        $key = $view['device'];
        $index = $open[$key] ?? null;
        if ($index === null || $view['ts'] > $visits[$index]['end'] + VISIT_GAP) {
            $visits[] = [
                'device' => $key, 'start' => $view['ts'], 'end' => $view['ts'], 'seconds' => 0,
                'pages' => [], 'referrer' => $view['referrer'],
            ];
            $index = $open[$key] = count($visits) - 1;
        }
        $visit = &$visits[$index];
        $visit['end'] = max($visit['end'], $view['last'], $view['ts'] + $view['seconds']);
        $visit['seconds'] += $view['seconds'];
        $sections = array_map(fn($id) => SECTIONS[$id] ?? $id, $view['sections']);
        $visit['pages'][] = page_label($view['page']) . ($sections ? ' (' . implode(', ', $sections) . ')' : '');
        unset($visit);
    }
    return $visits;
}

/** Resumen por aparato: visitas, tiempo total y última visita. */
function build_devices(array $views, array $visits): array
{
    $devices = [];
    foreach ($views as $view) {
        $devices[$view['device']] ??= [
            'label' => describe_device($view['ua'], $view['screen']),
            'visits' => 0, 'seconds' => 0, 'first' => $view['ts'], 'last' => $view['ts'],
        ];
    }
    foreach ($visits as $visit) {
        $device = &$devices[$visit['device']];
        $device['visits']++;
        $device['seconds'] += $visit['seconds'];
        $device['last'] = max($device['last'], $visit['end']);
        unset($device);
    }
    uasort($devices, fn($a, $b) => $b['last'] <=> $a['last']);
    return $devices;
}

function duration(int $seconds): string
{
    if ($seconds < 60) {
        return "$seconds s";
    }
    $minutes = intdiv($seconds, 60);
    return $minutes < 60 ? "$minutes min" : intdiv($minutes, 60) . ' h ' . ($minutes % 60) . ' min';
}

function when(int $ts): string
{
    return DAYS[(int) date('w', $ts)] . ' ' . date('d/m H:i', $ts);
}

/** Estado del aviso por Telegram: si está activado y cómo fue el último envío. */
function telegram_status(bool $configured, array $state): string
{
    if (!$configured) {
        return 'Aviso por Telegram desactivado: faltan los secretos TELEGRAM_TOKEN y TELEGRAM_CHAT_ID.';
    }
    $last = $state['last'] ?? null;
    if (!is_array($last)) {
        return 'Aviso por Telegram activado, todavía sin envíos.';
    }
    if ($last['result'] === 'ok') {
        return 'Aviso por Telegram: último envío correcto, ' . when($last['ts']) . '.';
    }
    return 'Aviso por Telegram: falló el último envío, ' . when($last['ts']) . " ({$last['result']}).";
}

function e(string $text): string
{
    return htmlspecialchars($text, ENT_QUOTES, 'UTF-8');
}

function save_names(string $file, array $names): void
{
    // JSON_INVALID_UTF8_SUBSTITUTE: un carácter raro se sustituye en vez de dejar el JSON vacío.
    $json = json_encode($names, JSON_HEX_TAG | JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
    file_put_contents($file, DATA_HEADER . $json . "\n", LOCK_EX);
}

// Al cargarlo desde los tests (PHP en modo consola) solo se definen las funciones.
if (PHP_SAPI === 'cli') {
    return;
}

date_default_timezone_set('Europe/Madrid');
header('X-Robots-Tag: noindex, nofollow');
header('Cache-Control: no-store');
$dataDir = __DIR__ . '/datos';
$namesFile = "$dataDir/aparatos.php";
$hashFile = __DIR__ . '/informe-clave.php';
$hash = file_exists($hashFile) ? include $hashFile : null;
$password = is_string($_POST['clave'] ?? null) ? $_POST['clave'] : '';
$allowed = is_string($hash) && $password !== '' && password_verify($password, $hash);
if ($password !== '' && !$allowed) {
    sleep(1); // Frena a quien pruebe contraseñas a ciegas.
}

if ($allowed && isset($_POST['nombres']) && is_array($_POST['nombres'])) {
    $names = read_data($namesFile);
    foreach ($_POST['nombres'] as $key => $name) {
        if (is_string($key) && preg_match('/^[0-9a-f]{6}$/', $key) && is_string($name)) {
            // Hasta 40 caracteres. Con preg y no con mb_substr, que no todos los hostings tienen.
            // Si el texto no es UTF-8 válido, preg falla y se corta por bytes.
            $name = trim($name);
            $names[$key] = [
                'name' => preg_match('/^.{0,40}/su', $name, $cut) ? $cut[0] : substr($name, 0, 40),
                'me' => isset($_POST['yo'][$key]),
            ];
        }
    }
    save_names($namesFile, $names);
}
?>
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>Diario de visitas</title>
  <link rel="stylesheet" href="style.css">
  <style>
    .report { max-width: 1100px; margin: 0 auto; padding: 16px; }
    .report h1 { font: 700 1.8rem/1.1 var(--display); text-transform: uppercase; color: var(--primary); }
    .report section { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 4px 16px 16px; margin-bottom: 16px; }
    .report .wrap { overflow-x: auto; }
    .report table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
    .report th, .report td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
    .report .num { text-align: right; white-space: nowrap; }
    .report .muted { color: var(--muted); }
    .report .me { opacity: 0.55; }
    .report .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
    .report .tile b { display: block; font: 700 1.8rem/1.1 var(--display); color: var(--primary); }
    .report input[type=text], .report input[type=password] { font: inherit; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; max-width: 100%; }
    .report button { font: inherit; font-weight: 600; padding: 8px 14px; border: 0; border-radius: 6px; background: var(--primary); color: #fff; cursor: pointer; }
  </style>
</head>
<body>
<main class="report">
  <h1>Diario de visitas</h1>
<?php if (!is_string($hash)): ?>
  <section><p>El informe está desactivado: falta el secreto <code>INFORME_CLAVE</code> en GitHub. Créalo y vuelve a publicar la web.</p></section>
<?php elseif (!$allowed): ?>
  <section>
    <form method="post">
      <p><label>Contraseña<br><input type="password" name="clave" autocomplete="current-password" autofocus></label></p>
      <?php if ($password !== ''): ?><p class="muted">Contraseña incorrecta.</p><?php endif; ?>
      <p><button>Entrar</button></p>
    </form>
  </section>
<?php else:
    $views = build_views(read_records($dataDir));
    $visits = build_visits($views);
    $devices = build_devices($views, $visits);
    $names = read_data($namesFile);
    $isMe = fn(string $key) => $names[$key]['me'] ?? false;
    $nameOf = fn(string $key) => ($names[$key]['name'] ?? '') !== '' ? $names[$key]['name'] : $devices[$key]['label'];
    $others = array_values(array_filter($visits, fn($v) => !$isMe($v['device'])));
    $now = time();
    $online = array_unique(array_map(
        fn($v) => $v['device'],
        array_filter($views, fn($v) => $now - $v['last'] <= ONLINE_GAP && !$isMe($v['device']))
    ));
    $lastDays = fn(int $days) => array_filter($others, fn($v) => $v['start'] >= $now - $days * 86400);
    $deviceCount = fn(array $list) => count(array_unique(array_column($list, 'device')));
?>
  <p class="muted">Sin contar los aparatos marcados como "soy yo". Un aparato es un navegador en una pantalla: la misma persona con móvil y ordenador cuenta como dos.</p>
  <section>
    <h2>Resumen</h2>
    <div class="tiles">
      <div class="tile"><b><?= count($online) ?></b>conectados ahora</div>
      <div class="tile"><b><?= count($lastDays(7)) ?></b>visitas en 7 días</div>
      <div class="tile"><b><?= $deviceCount($lastDays(7)) ?></b>aparatos en 7 días</div>
      <div class="tile"><b><?= count($lastDays(30)) ?></b>visitas en 30 días</div>
      <div class="tile"><b><?= $deviceCount($lastDays(30)) ?></b>aparatos en 30 días</div>
      <div class="tile"><b><?= duration(array_sum(array_column($lastDays(30), 'seconds'))) ?></b>de lectura en 30 días</div>
    </div>
    <p class="muted"><?= e(telegram_status(file_exists(__DIR__ . '/telegram-config.php'), read_data("$dataDir/telegram.php"))) ?></p>
  </section>

  <section>
    <h2>Aparatos</h2>
    <form method="post">
      <input type="hidden" name="clave" value="<?= e($password) ?>">
      <div class="wrap"><table>
        <tr><th>Nombre</th><th>Aparato</th><th class="num">Visitas</th><th class="num">Tiempo</th><th>Última</th><th>Soy yo</th></tr>
        <?php foreach ($devices as $key => $d): ?>
        <tr<?= $isMe($key) ? ' class="me"' : '' ?>>
          <td><input type="text" name="nombres[<?= e($key) ?>]" value="<?= e($names[$key]['name'] ?? '') ?>" placeholder="¿Quién?" size="12"></td>
          <td><?= e($d['label']) ?></td>
          <td class="num"><?= $d['visits'] ?></td>
          <td class="num"><?= duration($d['seconds']) ?></td>
          <td><?= when($d['last']) ?></td>
          <td><input type="checkbox" name="yo[<?= e($key) ?>]"<?= $isMe($key) ? ' checked' : '' ?>></td>
        </tr>
        <?php endforeach; ?>
      </table></div>
      <p><button>Guardar nombres</button></p>
    </form>
  </section>

  <section>
    <h2>Visitas</h2>
    <p class="muted">El tiempo es el que la página estuvo a la vista (se mide cada 30 segundos). Las secciones son las de la portada que pasaron por el centro de la pantalla.</p>
    <div class="wrap"><table>
      <tr><th>Cuándo</th><th>Quién</th><th class="num">Tiempo</th><th>Páginas</th></tr>
      <?php foreach (array_slice(array_reverse($others), 0, MAX_VISITS) as $v): ?>
      <tr>
        <td><?= when($v['start']) ?></td>
        <td><?= e($nameOf($v['device'])) ?><?php if ($v['referrer'] !== '' && $v['referrer'] !== ($_SERVER['HTTP_HOST'] ?? '')): ?><br><span class="muted">desde <?= e($v['referrer']) ?></span><?php endif; ?></td>
        <td class="num"><?= duration($v['seconds']) ?></td>
        <td><?= e(implode(' → ', $v['pages'])) ?></td>
      </tr>
      <?php endforeach; ?>
    </table></div>
  </section>
<?php endif; ?>
</main>
</body>
</html>
