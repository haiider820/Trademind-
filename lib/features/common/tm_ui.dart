import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:trademind_ai/core/theme/app_theme.dart';

class TmBackground extends StatelessWidget {
  const TmBackground({super.key, required this.child, this.padding});

  final Widget child;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppTheme.background, Color(0xFF10102A), AppTheme.background],
          stops: [0, 0.42, 1],
        ),
      ),
      child: Stack(
        children: [
          const Positioned(
            top: -110,
            right: -80,
            child: _AmbientOrb(color: AppTheme.magenta, size: 260),
          ),
          const Positioned(
            top: 210,
            left: -140,
            child: _AmbientOrb(color: AppTheme.purple, size: 300),
          ),
          Positioned.fill(
            child: Padding(
              padding: padding ?? EdgeInsets.zero,
              child: child,
            ),
          ),
        ],
      ),
    );
  }
}

class _AmbientOrb extends StatelessWidget {
  const _AmbientOrb({required this.color, required this.size});

  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: ImageFiltered(
        imageFilter: ImageFilter.blur(sigmaX: 54, sigmaY: 54),
        child: DecoratedBox(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: color.withValues(alpha: 0.14),
          ),
          child: SizedBox(width: size, height: size),
        ),
      ),
    );
  }
}

class TmGlassPanel extends StatelessWidget {
  const TmGlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.borderRadius = 24,
    this.accent,
    this.margin,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double borderRadius;
  final Color? accent;
  final EdgeInsetsGeometry? margin;

  @override
  Widget build(BuildContext context) {
    final glow = accent ?? AppTheme.purple;
    return Container(
      margin: margin,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(borderRadius),
        boxShadow: [
          BoxShadow(
            color: glow.withValues(alpha: 0.11),
            blurRadius: 28,
            spreadRadius: -9,
            offset: const Offset(0, 12),
          ),
          const BoxShadow(
            color: Color(0x66000000),
            blurRadius: 18,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(borderRadius),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
          child: Container(
            padding: padding,
            decoration: BoxDecoration(
              color: AppTheme.panel.withValues(alpha: 0.92),
              borderRadius: BorderRadius.circular(borderRadius),
              border: Border.all(color: glow.withValues(alpha: 0.2)),
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Colors.white.withValues(alpha: 0.055),
                  AppTheme.panel.withValues(alpha: 0.96),
                ],
              ),
            ),
            child: child,
          ),
        ),
      ),
    );
  }
}

class TmPressable extends StatefulWidget {
  const TmPressable({
    super.key,
    required this.child,
    required this.onTap,
    this.borderRadius = 24,
    this.scale = 0.975,
  });

  final Widget child;
  final VoidCallback onTap;
  final double borderRadius;
  final double scale;

  @override
  State<TmPressable> createState() => _TmPressableState();
}

class _TmPressableState extends State<TmPressable> {
  bool _pressed = false;

  void _setPressed(bool value) {
    if (mounted) setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: widget.onTap,
      onTapDown: (_) => _setPressed(true),
      onTapCancel: () => _setPressed(false),
      onTapUp: (_) => _setPressed(false),
      child: AnimatedScale(
        scale: _pressed ? widget.scale : 1,
        duration: const Duration(milliseconds: 110),
        curve: Curves.easeOutCubic,
        child: widget.child,
      ),
    );
  }
}

class TmClayCard extends StatelessWidget {
  const TmClayCard({
    super.key,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.all(16),
    this.accent,
    this.borderRadius = 24,
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;
  final Color? accent;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    final panel = TmGlassPanel(
      padding: padding,
      borderRadius: borderRadius,
      accent: accent,
      child: child,
    );
    if (onTap == null) return panel;
    return TmPressable(borderRadius: borderRadius, onTap: onTap!, child: panel);
  }
}

class TmMetricTile extends StatelessWidget {
  const TmMetricTile({
    super.key,
    required this.label,
    required this.value,
    required this.accent,
    this.icon,
    this.flex = 1,
  });

  final String label;
  final String value;
  final Color accent;
  final IconData? icon;
  final int flex;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      flex: flex,
      child: TmGlassPanel(
        padding: const EdgeInsets.all(13),
        borderRadius: 19,
        accent: accent,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (icon != null) ...[
                  Icon(icon, size: 15, color: accent),
                  const SizedBox(width: 6),
                ],
                Expanded(
                  child: Text(
                    label.toUpperCase(),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: AppTheme.muted,
                          letterSpacing: 0.8,
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: AppTheme.text,
                    fontWeight: FontWeight.w900,
                    letterSpacing: -0.25,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class TmSectionHeader extends StatelessWidget {
  const TmSectionHeader({super.key, required this.title, this.subtitle, this.trailing});

  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: AppTheme.text,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.35,
                    ),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: 4),
                Text(subtitle!, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.muted)),
              ],
            ],
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

class TmLoadingState extends StatelessWidget {
  const TmLoadingState({super.key, this.label = 'Syncing live market data'});

  final String label;

  @override
  Widget build(BuildContext context) {
    return TmGlassPanel(
      accent: AppTheme.magenta,
      child: Row(
        children: [
          const SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2.4, color: AppTheme.magenta),
          ),
          const SizedBox(width: 12),
          Expanded(child: Text(label, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.muted))),
        ],
      ),
    );
  }
}

class TmEmptyState extends StatelessWidget {
  const TmEmptyState({super.key, required this.title, required this.subtitle, required this.icon});

  final String title;
  final String subtitle;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return TmGlassPanel(
      accent: AppTheme.purple,
      child: Column(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppTheme.purple.withValues(alpha: 0.14),
              border: Border.all(color: AppTheme.purple.withValues(alpha: 0.32)),
            ),
            child: const Icon(Icons.auto_awesome, color: AppTheme.purple),
          ),
          const SizedBox(height: 12),
          Text(title, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 5),
          Text(subtitle, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.muted)),
          const SizedBox(height: 8),
          Icon(icon, size: 18, color: AppTheme.muted),
        ],
      ),
    );
  }
}

class TmAnimatedValue extends StatelessWidget {
  const TmAnimatedValue({super.key, required this.value, required this.style, this.color});

  final String value;
  final TextStyle? style;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 240),
      transitionBuilder: (child, animation) => FadeTransition(
        opacity: animation,
        child: SlideTransition(
          position: Tween<Offset>(begin: const Offset(0, 0.16), end: Offset.zero).animate(animation),
          child: child,
        ),
      ),
      child: Text(
        value,
        key: ValueKey(value),
        style: style?.copyWith(color: color) ?? TextStyle(color: color),
      ),
    );
  }
}
