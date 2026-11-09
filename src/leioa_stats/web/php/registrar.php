<?php
// Recibe los avisos de visits.js y los apunta, uno por línea, en datos/visitas-AAAA-MM.php.
//
// Qué se guarda: la hora, la página, el tiempo visible, las secciones vistas y el aparato
// (navegador y pantalla). No se guarda la IP ni nada que identifique a la persona.
//
// Por qué el archivo de datos acaba en .php: su primera línea es un "exit" de PHP. Si alguien
// lo pide desde internet, el servidor lo ejecuta, se para en esa línea y no muestra nada. Es
// una protección que no depende de la configuración del servidor; datos/.htaccess es otra más.

declare(strict_types=1);

const MAX_BODY = 2048;              // Un aviso ocupa unos 200 bytes.
const MAX_FILE = 5 * 1024 * 1024;   // Tope por mes, por si alguien envía avisos falsos.
const HEADER = "<?php http_response_code(404); exit; ?>\n";
const HTACCESS = "<IfModule mod_authz_core.c>\n  Require all denied\n</IfModule>\n"
    . "<IfModule !mod_authz_core.c>\n  Order allow,deny\n  Deny from all\n</IfModule>\n";

function finish(int $status): void
{
    http_response_code($status);
    exit;
}

/** Comprueba el aviso y devuelve la línea que se guarda, o null si no es válido. */
function build_record(array $data, string $userAgent, int $now): ?array
{
    $view = $data['v'] ?? null;
    if (!is_string($view) || !preg_match('/^[a-z0-9]{6,30}$/', $view)) {
        return null;
    }
    $record = ['ts' => $now, 'v' => $view, 't' => $data['t'] ?? null];
    switch ($record['t']) {
        case 'start':
            $page = $data['p'] ?? null;
            $referrer = $data['r'] ?? '';
            $screen = $data['w'] ?? '';
            if (!is_string($page) || !preg_match('#^/[\w./\#%-]{0,200}$#u', $page)) {
                return null;
            }
            if (!is_string($referrer) || !preg_match('/^[a-z0-9.-]{0,100}$/i', $referrer)) {
                return null;
            }
            if (!is_string($screen) || !preg_match('/^\d{2,5}x\d{2,5}@[\d.]{1,5}$/', $screen)) {
                return null;
            }
            $record += ['p' => $page, 'r' => $referrer, 'w' => $screen, 'ua' => substr($userAgent, 0, 300)];
            return $record;
        case 'ping':
            $seconds = $data['s'] ?? null;
            if (!is_int($seconds) || $seconds < 0 || $seconds > 12 * 3600) {
                return null;
            }
            return $record + ['s' => $seconds];
        case 'section':
            $id = $data['id'] ?? null;
            if (!is_string($id) || !preg_match('/^[a-z0-9_-]{1,40}$/', $id)) {
                return null;
            }
            return $record + ['id' => $id];
        default:
            return null;
    }
}

/** Añade la línea al archivo del mes, creando la carpeta y su protección si hace falta. */
function append_record(string $dir, array $record): void
{
    if (!is_dir($dir)) {
        mkdir($dir, 0750, true);
    }
    if (!file_exists("$dir/.htaccess")) {
        file_put_contents("$dir/.htaccess", HTACCESS);
    }
    $file = $dir . '/visitas-' . date('Y-m', $record['ts']) . '.php';
    if (file_exists($file) && filesize($file) > MAX_FILE) {
        return;
    }
    // JSON_HEX_TAG convierte < y > en < y >: así nada de lo recibido puede
    // parecer código PHP dentro del archivo.
    $line = json_encode($record, JSON_HEX_TAG | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    $handle = fopen($file, 'a');
    if ($handle === false) {
        return;
    }
    // El bloqueo evita que dos avisos a la vez mezclen sus líneas.
    flock($handle, LOCK_EX);
    if (fstat($handle)['size'] === 0) {
        fwrite($handle, HEADER);
    }
    fwrite($handle, $line . "\n");
    flock($handle, LOCK_UN);
    fclose($handle);
}

// Al cargarlo desde los tests (PHP en modo consola) solo se definen las funciones.
if (PHP_SAPI === 'cli') {
    return;
}

date_default_timezone_set('Europe/Madrid');
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    finish(405);
}
$body = file_get_contents('php://input', false, null, 0, MAX_BODY + 1);
if ($body === false || strlen($body) > MAX_BODY) {
    finish(400);
}
$data = json_decode($body, true);
$record = is_array($data) ? build_record($data, $_SERVER['HTTP_USER_AGENT'] ?? '', time()) : null;
if ($record === null) {
    finish(400);
}
append_record(__DIR__ . '/datos', $record);
finish(204);
