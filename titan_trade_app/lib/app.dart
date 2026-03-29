import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'providers/config_provider.dart';
import 'screens/dashboard_screen.dart';
import 'screens/near_miss_detail_screen.dart';
import 'screens/near_misses_screen.dart';
import 'screens/setup_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/statistics_screen.dart';
import 'screens/theses_screen.dart';
import 'screens/thesis_detail_screen.dart';
import 'screens/trade_detail_screen.dart';
import 'screens/trade_history_screen.dart';
import 'screens/watchlist_screen.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();
final _shellNavigatorKey = GlobalKey<NavigatorState>();

final appRouter = GoRouter(
  navigatorKey: _rootNavigatorKey,
  initialLocation: '/',
  redirect: (context, state) => null,
  routes: [
    ShellRoute(
      navigatorKey: _shellNavigatorKey,
      builder: (context, state, child) => AppShell(child: child),
      routes: [
        GoRoute(path: '/', builder: (context, state) => const DashboardScreen()),
        GoRoute(path: '/theses', builder: (context, state) => const ThesesScreen()),
        GoRoute(
          path: '/theses/:ticker',
          builder: (context, state) =>
              ThesisDetailScreen(ticker: state.pathParameters['ticker']!),
        ),
        GoRoute(path: '/trades', builder: (context, state) => const TradeHistoryScreen()),
        GoRoute(
          path: '/trades/:index',
          builder: (context, state) =>
              TradeDetailScreen(tradeIndex: int.parse(state.pathParameters['index']!)),
        ),
        GoRoute(path: '/near-misses', builder: (context, state) => const NearMissesScreen()),
        GoRoute(
          path: '/near-misses/:index',
          builder: (context, state) =>
              NearMissDetailScreen(nearMissIndex: int.parse(state.pathParameters['index']!)),
        ),
        GoRoute(path: '/watchlist', builder: (context, state) => const WatchlistScreen()),
        GoRoute(path: '/statistics', builder: (context, state) => const StatisticsScreen()),
        GoRoute(path: '/settings', builder: (context, state) => const SettingsScreen()),
      ],
    ),
  ],
);

class AppShell extends ConsumerWidget {
  final Widget child;

  const AppShell({super.key, required this.child});

  static const _destinations = [
    NavigationRailDestination(icon: Icon(Icons.dashboard), label: Text('Dashboard')),
    NavigationRailDestination(icon: Icon(Icons.analytics), label: Text('Theses')),
    NavigationRailDestination(icon: Icon(Icons.receipt_long), label: Text('Trades')),
    NavigationRailDestination(icon: Icon(Icons.block), label: Text('Near Misses')),
    NavigationRailDestination(icon: Icon(Icons.list_alt), label: Text('Watchlist')),
    NavigationRailDestination(icon: Icon(Icons.bar_chart), label: Text('Statistics')),
    NavigationRailDestination(icon: Icon(Icons.settings), label: Text('Settings')),
  ];

  static const _routes = ['/', '/theses', '/trades', '/near-misses', '/watchlist', '/statistics', '/settings'];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pathAsync = ref.watch(dataPathProvider);

    return pathAsync.when(
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(body: Center(child: Text('Error: $e'))),
      data: (path) {
        if (path == null) return const SetupScreen();

        final currentPath = GoRouterState.of(context).uri.path;
        // Match the most specific route (longest prefix match)
        int selectedIndex = 0;
        for (int i = _routes.length - 1; i >= 0; i--) {
          if (_routes[i] == '/' ? currentPath == '/' : currentPath.startsWith(_routes[i])) {
            selectedIndex = i;
            break;
          }
        }

        return Scaffold(
          body: Row(
            children: [
              NavigationRail(
                selectedIndex: selectedIndex,
                onDestinationSelected: (index) => context.go(_routes[index]),
                labelType: NavigationRailLabelType.all,
                leading: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  child: Text(
                    'TT',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                  ),
                ),
                destinations: _destinations,
              ),
              const VerticalDivider(thickness: 1, width: 1),
              Expanded(child: child),
            ],
          ),
        );
      },
    );
  }
}
