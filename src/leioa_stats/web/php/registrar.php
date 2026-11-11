<?php
// Recibe los avisos de visits.js y los apunta, uno por línea, en datos/visitas-AAAA-MM.php.
//
// Qué se guarda: la hora, la página, el tiempo visible, las secciones vistas y el aparato
// (navegador y pantalla). No se guarda la IP ni nada que identifique a la persona.
//
// Por qué el archivo de datos acaba en .php: su primera línea es un "exit" de PHP. Si alguien
// lo pide desde internet, el servidor lo ejecuta, se para en esa línea y no muestra nada. Es
// una protección que no depende de la configuración del servidor; datos/.htaccess es otra más.
//
// Aviso por Telegram: si existe telegram-config.php (lo crea la publicación con los secretos
// TELEGRAM_TOKEN y TELEGRAM_CHAT_ID), cada visita nueva manda un mensaje. Una visita es la de
// informe.php: mismo aparato y menos de 30 minutos entre páginas. No avisa de los aparatos
// marcados como "soy yo" en el informe y manda como mucho MAX_ALERTS_PER_HOUR por hora.

declare(strict_types=1);

require_once __DIR__ . '/comun.php';

const MAX_BODY = 2048;              // Un aviso ocupa unos 200 bytes.
const MAX_FILE = 5 * 1024 * 1024;   // Tope por mes, por si alguien envía avisos falsos.
const MAX_ALERTS_PER_HOUR = 10;     // Por si alguien envía avisos falsos: el móvil no se llena.
const TELEGRAM_TIMEOUT = 3;         // Segundos como mucho esperando a Telegram.
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
        fwrite($handle, DATA_HEADER);
    }
    fwrite($handle, $line . "\n");
    flock($handle, LOCK_UN);
    fclose($handle);
}

/**
 * Texto del aviso de una visita nueva, o null si el aparato está marcado como "soy yo".
 * $names son los nombres que el usuario pone a sus aparatos en el informe.
 */
function alert_text(array $record, array $names): ?string
{
    $device = device_key($record['ua'], $record['w']);
    if ($names[$device]['me'] ?? false) {
        return null;
    }
    $label = describe_device($record['ua'], $record['w']);
    $name = $names[$device]['name'] ?? '';
    $lines = [
        'Nueva visita a la web del Leioa',
        $name !== '' ? "$name ($label)" : $label,
        page_label($record['p']) . ' · ' . date('H:i', $record['ts']),
    ];
    if ($record['r'] !== '') {
        $lines[] = 'Llega desde ' . $record['r'];
    }
    return implode("\n", $lines);
}

/**
 * Decide si se avisa y devuelve [avisar, estado nuevo]. El estado guarda cuándo se vio por
 * última vez cada aparato y la hora de los avisos enviados en la última hora.
 */
function alert_decision(array $state, string $device, int $now): array
{
    $last = $state['devices'][$device] ?? null;
    // Cada página vista alarga la visita: el reloj de los 30 minutos vuelve a empezar.
    $devices = array_filter($state['devices'] ?? [], fn($ts) => $now - $ts <= VISIT_GAP);
    $devices[$device] = $now;
    $sent = array_values(array_filter($state['sent'] ?? [], fn($ts) => $now - $ts < 3600));
    $alert = ($last === null || $now - $last > VISIT_GAP) && count($sent) < MAX_ALERTS_PER_HOUR;
    if ($alert) {
        $sent[] = $now;
    }
    return [$alert, ['devices' => $devices, 'sent' => $sent] + $state];
}

/**
 * Lee el estado de los avisos (datos/telegram.php), le aplica $change y lo guarda, con el
 * archivo bloqueado. $change recibe el estado y devuelve [resultado, estado nuevo].
 */
function update_alert_state(string $file, callable $change)
{
    $handle = fopen($file, 'c+');
    if ($handle === false) {
        return null;
    }
    // El bloqueo evita que dos páginas abiertas a la vez manden dos avisos.
    flock($handle, LOCK_EX);
    $lines = explode("\n", (string) stream_get_contents($handle));
    $state = json_decode($lines[1] ?? '', true) ?: [];
    [$result, $state] = $change($state);
    ftruncate($handle, 0);
    rewind($handle);
    fwrite($handle, DATA_HEADER . json_encode($state, JSON_HEX_TAG | JSON_UNESCAPED_UNICODE) . "\n");
    flock($handle, LOCK_UN);
    fclose($handle);
    return $result;
}

/** Envía el texto por Telegram. Devuelve "ok" o una descripción corta del fallo. */
function send_telegram(string $token, string $chatId, string $text): string
{
    $url = "https://api.telegram.org/bot$token/sendMessage";
    $body = http_build_query(['chat_id' => $chatId, 'text' => $text]);
    // curl es lo habitual en los hostings; si no está, se usa la función de archivos de PHP.
    if (function_exists('curl_init')) {
        $curl = curl_init($url);
        curl_setopt_array($curl, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $body,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => TELEGRAM_TIMEOUT,
        ]);
        $response = curl_exec($curl);
        $status = (int) curl_getinfo($curl, CURLINFO_HTTP_CODE);
        $error = curl_error($curl);
    } else {
        $context = stream_context_create(['http' => [
            'method' => 'POST',
            'header' => 'Content-Type: application/x-www-form-urlencoded',
            'content' => $body,
            'timeout' => TELEGRAM_TIMEOUT,
            'ignore_errors' => true,
        ]]);
        $response = @file_get_contents($url, false, $context);
        $first = $http_response_header[0] ?? '';
        $status = preg_match('#^HTTP/\S+ (\d{3})#', $first, $m) ? (int) $m[1] : 0;
        // Sin conexión, PHP explica el motivo (por ejemplo, allow_url_fopen desactivado).
        $error = $response === false ? (error_get_last()['message'] ?? 'sin conexión') : '';
    }
    if ($status === 200) {
        return 'ok';
    }
    // Telegram explica el fallo en "description" (por ejemplo, "chat not found").
    $answer = is_string($response) ? json_decode($response, true) : null;
    $description = is_array($answer) ? (string) ($answer['description'] ?? '') : '';
    // Los errores de PHP repiten la dirección, que lleva el token: se tapa antes de guardarlo.
    return str_replace($token, '<token>', trim("error $status " . ($description !== '' ? $description : $error)));
}

/** Manda el aviso de la visita si toca. Se llama después de responder: el visitante no espera. */
function notify_visit(string $configFile, string $dir, array $record): void
{
    $config = file_exists($configFile) ? include $configFile : null;
    $token = $config['token'] ?? '';
    $chatId = $config['chat'] ?? '';
    // El token tiene la forma "números:letras". Se comprueba para no montar una dirección rara.
    if (!is_string($token) || !preg_match('/^\d+:[\w-]+$/', $token)
        || !is_string($chatId) || !preg_match('/^-?\d+$/', $chatId)) {
        return;
    }
    $text = alert_text($record, read_data("$dir/aparatos.php"));
    if ($text === null) {
        return;
    }
    $stateFile = "$dir/telegram.php";
    $device = device_key($record['ua'], $record['w']);
    $alert = update_alert_state($stateFile, fn(array $state) => alert_decision($state, $device, $record['ts']));
    if ($alert !== true) {
        return;
    }
    $result = send_telegram($token, $chatId, $text);
    // El resultado del último envío sale en el informe: así se sabe si el hosting deja salir.
    $last = ['ts' => time(), 'result' => substr($result, 0, 200)];
    update_alert_state($stateFile, fn(array $state) => [null, ['last' => $last] + $state]);
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
if ($record['t'] !== 'start') {
    finish(204);
}
// Se responde ya y el aviso se manda después, para que el navegador no espere a Telegram.
http_response_code(204);
ignore_user_abort(true);
if (function_exists('fastcgi_finish_request')) {
    fastcgi_finish_request();
}
notify_visit(__DIR__ . '/telegram-config.php', __DIR__ . '/datos', $record);
