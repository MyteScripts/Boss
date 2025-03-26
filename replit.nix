
{pkgs}: {
  deps = [
    pkgs.libopus
    pkgs.libsodium
    pkgs.ffmpeg
    pkgs.ffmpeg-full
    pkgs.sqlite
    pkgs.postgresql
    pkgs.openssl
  ];
}
