<?php
// Piezas comunes del diario de visitas: las usan informe.php (el informe) y registrar.php (el
// aviso por Telegram). Solo define constantes y funciones: abierto desde internet no muestra nada.
//
// Compatible con PHP 7.4 o posterior (no se conoce la versión exacta del hosting).

declare(strict_types=1);

// Primera línea de los archivos de datos: si alguien los pide desde internet, el servidor los
// ejecuta, se para aquí y no muestra nada.
const DATA_HEADER = "<?php http_response_code(404); exit; ?>\n";
const VISIT_GAP = 30 * 60;   // Más de 30 minutos sin actividad: empieza otra visita.

const PAGES = [
    'index.html' => 'Resumen',
    'jugadores.html' => 'Jugadores',
    'comparativa.html' => 'Comparativa',
];
const SECTIONS = [
    'partidos' => 'Partidos',
    'cuartos' => 'Cuartos',
    'origen' => 'Origen de los puntos',
    'tiro' => 'Tiro',
    'quintetos' => 'Quintetos',
    'liga' => 'Liga',
    'glosario' => 'Glosario',
];

/** Código corto del aparato: mismo navegador y misma pantalla, mismo código. */
function device_key(string $userAgent, string $screen): string
{
    return substr(md5($userAgent . '|' . $screen), 0, 6);
}

/** Descripción legible del aparato a partir del navegador y la pantalla. */
function describe_device(string $ua, string $screen): string
{
    if (preg_match('/iPhone OS (\d+)/', $ua, $m)) {
        $system = "iPhone · iOS $m[1]";
    } elseif (preg_match('/iPad.*OS (\d+)/', $ua, $m)) {
        $system = "iPad · iOS $m[1]";
    } elseif (preg_match('/Android (\d+)(?:[^;)]*;\s*([^;)]+?)(?:\sBuild[^;)]*)?\))?/', $ua, $m)) {
        $model = isset($m[2]) && $m[2] !== 'K' ? ' ' . trim($m[2]) : '';
        $system = "Android $m[1]$model";
    } elseif (strpos($ua, 'Windows') !== false) {
        $system = 'Ordenador Windows';
    } elseif (strpos($ua, 'Macintosh') !== false) {
        $system = 'Mac';
    } elseif (strpos($ua, 'Linux') !== false) {
        $system = 'Linux';
    } else {
        $system = 'Aparato desconocido';
    }
    $browsers = [
        'Edg' => 'Edge', 'SamsungBrowser' => 'Samsung Internet', 'CriOS' => 'Chrome',
        'FxiOS' => 'Firefox', 'Firefox' => 'Firefox', 'Chrome' => 'Chrome', 'Safari' => 'Safari',
    ];
    $browser = 'otro navegador';
    foreach ($browsers as $token => $name) {
        if (strpos($ua, $token) !== false) {
            $browser = $name;
            break;
        }
    }
    $size = explode('@', $screen)[0];
    return "$system · $browser · " . str_replace('x', '×', $size);
}

/** Nombre de una página (y su sección, si se abrió con #) a partir de su ruta. */
function page_label(string $path): string
{
    [$path, $hash] = array_pad(explode('#', $path, 2), 2, '');
    if (preg_match('#/partidos/(\d+)\.html$#', $path, $m)) {
        $label = "Partido $m[1]";
    } elseif (preg_match('#/equipos/([\w-]+)\.html$#', $path, $m)) {
        $label = 'Equipo ' . str_replace('-', ' ', $m[1]);
    } else {
        $file = basename($path);
        $label = PAGES[$file === '' || strpos($file, '.') === false ?'index.html' : $file] ?? $file;
    }
    return $hash !== '' ? "$label › " . (SECTIONS[$hash] ?? $hash) : $label;
}

/** Lee un archivo de datos con la cabecera protectora y una línea JSON (nombres, avisos). */
function read_data(string $file): array
{
    if (!file_exists($file)) {
        return [];
    }
    $lines = file($file, FILE_IGNORE_NEW_LINES);
    return json_decode($lines[1] ?? '{}', true) ?: [];
}
