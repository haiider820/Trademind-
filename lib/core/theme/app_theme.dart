import 'package:flutter/material.dart';

class AppTheme {
  static const _bg = Color(0xFF0A0D14);
  static const _surface = Color(0xFF111827);
  static const _elevated = Color(0xFF1C2333);
  static const _primary = Color(0xFF00E676);
  static const _red = Color(0xFFFF3D57);
  static const _blue = Color(0xFF4D9FFF);
  static const _text = Color(0xFFF0F4FF);
  static const _muted = Color(0xFF8891A7);

  static ThemeData darkTheme() {
    final scheme = const ColorScheme.dark(
      primary: _primary,
      secondary: _blue,
      surface: _surface,
      error: _red,
      onPrimary: Colors.black,
      onSecondary: Colors.white,
      onSurface: _text,
      onError: Colors.white,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: _bg,
      colorScheme: scheme,
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: _text,
        elevation: 0,
        scrolledUnderElevation: 0,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: _surface.withValues(alpha: 0.82),
        indicatorColor: _primary.withValues(alpha: 0.15),
        labelTextStyle: WidgetStateProperty.all(
          const TextStyle(color: _muted, fontSize: 12, fontWeight: FontWeight.w600),
        ),
      ),
      cardTheme: CardThemeData(
        color: _surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: _elevated,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: _elevated,
        selectedColor: _primary.withValues(alpha: 0.15),
        side: const BorderSide(color: Color(0xFF1E2A3D)),
        labelStyle: const TextStyle(color: _text),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: _elevated,
        hintStyle: const TextStyle(color: _muted),
        labelStyle: const TextStyle(color: _muted),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: Color(0xFF1E2A3D)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: _blue, width: 1.2),
        ),
      ),
      textTheme: const TextTheme(
        headlineLarge: TextStyle(color: _text, fontWeight: FontWeight.w700),
        headlineMedium: TextStyle(color: _text, fontWeight: FontWeight.w700),
        headlineSmall: TextStyle(color: _text, fontWeight: FontWeight.w700),
        titleLarge: TextStyle(color: _text, fontWeight: FontWeight.w700),
        titleMedium: TextStyle(color: _text, fontWeight: FontWeight.w600),
        bodyLarge: TextStyle(color: _text),
        bodyMedium: TextStyle(color: _text),
        bodySmall: TextStyle(color: _muted),
      ),
      dividerTheme: const DividerThemeData(color: Color(0xFF1E2A3D)),
      iconTheme: const IconThemeData(color: _text),
      visualDensity: VisualDensity.standard,
    );
  }
}
