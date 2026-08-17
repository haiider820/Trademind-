import 'package:flutter/material.dart';

class AppTheme {
  static const background = Color(0xFF0B0C1E);
  static const panel = Color(0xFF1A1B35);
  static const elevated = Color(0xFF24234A);
  static const magenta = Color(0xFFFF007A);
  static const purple = Color(0xFF9D4EDD);
  static const gold = Color(0xFFFFB703);
  static const mint = Color(0xFF72F2C3);
  static const text = Color(0xFFF8F5FF);
  static const muted = Color(0xFFA8A3BC);
  static const outline = Color(0xFF34335E);

  static ThemeData darkTheme() {
    final scheme = const ColorScheme.dark(
      primary: magenta,
      secondary: purple,
      tertiary: gold,
      surface: panel,
      error: gold,
      onPrimary: Colors.white,
      onSecondary: Colors.white,
      onTertiary: background,
      onSurface: text,
      onError: background,
    );

    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: background,
      colorScheme: scheme,
      fontFamily: 'Inter',
    );

    return base.copyWith(
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: text,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: panel.withValues(alpha: 0.92),
        elevation: 0,
        height: 76,
        indicatorColor: magenta.withValues(alpha: 0.18),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => TextStyle(
            color: states.contains(WidgetState.selected) ? text : muted,
            fontSize: 11,
            fontWeight: FontWeight.w800,
            letterSpacing: 0.2,
          ),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected) ? magenta : muted,
            size: 22,
          ),
        ),
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: magenta,
        foregroundColor: Colors.white,
        elevation: 12,
        shape: StadiumBorder(),
      ),
      cardTheme: CardThemeData(
        color: panel,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: elevated,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        dragHandleColor: outline,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: elevated,
        selectedColor: magenta.withValues(alpha: 0.18),
        side: BorderSide(color: outline.withValues(alpha: 0.8)),
        labelStyle: const TextStyle(color: text, fontWeight: FontWeight.w700),
        secondaryLabelStyle: const TextStyle(color: muted),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: elevated.withValues(alpha: 0.84),
        hintStyle: const TextStyle(color: muted),
        labelStyle: const TextStyle(color: muted),
        prefixIconColor: muted,
        suffixIconColor: muted,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(17), borderSide: BorderSide.none),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(17),
          borderSide: BorderSide(color: outline.withValues(alpha: 0.8)),
        ),
        focusedBorder: const OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(17)),
          borderSide: BorderSide(color: magenta, width: 1.2),
        ),
      ),
      textTheme: const TextTheme(
        displayLarge: TextStyle(color: text, fontWeight: FontWeight.w900, letterSpacing: -1.1),
        displayMedium: TextStyle(color: text, fontWeight: FontWeight.w900, letterSpacing: -0.8),
        headlineLarge: TextStyle(color: text, fontWeight: FontWeight.w900, letterSpacing: -0.55),
        headlineMedium: TextStyle(color: text, fontWeight: FontWeight.w900, letterSpacing: -0.45),
        headlineSmall: TextStyle(color: text, fontWeight: FontWeight.w800, letterSpacing: -0.2),
        titleLarge: TextStyle(color: text, fontWeight: FontWeight.w800),
        titleMedium: TextStyle(color: text, fontWeight: FontWeight.w700),
        titleSmall: TextStyle(color: muted, fontWeight: FontWeight.w700),
        bodyLarge: TextStyle(color: text, height: 1.35),
        bodyMedium: TextStyle(color: text, height: 1.35),
        bodySmall: TextStyle(color: muted, height: 1.35),
        labelLarge: TextStyle(color: text, fontWeight: FontWeight.w800),
        labelMedium: TextStyle(color: muted, fontWeight: FontWeight.w700),
        labelSmall: TextStyle(color: muted, fontWeight: FontWeight.w700),
      ),
      dividerTheme: const DividerThemeData(color: outline, thickness: 1),
      iconTheme: const IconThemeData(color: text),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: magenta,
        linearTrackColor: outline,
        circularTrackColor: outline,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: elevated,
        contentTextStyle: const TextStyle(color: text, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        behavior: SnackBarBehavior.floating,
      ),
      visualDensity: VisualDensity.standard,
    );
  }
}
