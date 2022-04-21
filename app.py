import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import time
from random import uniform


def get_playoff_data(start_year, end_year):
    # Get list of playoff teams
    df = pd.read_html('https://www.baseball-reference.com/postseason/')[0]

    # Clean Data
    df = df.loc[df['Series'] != 'Future'].dropna()
    df[['Year', 'Playoff Series']] = df['Series'].str.split(' ', 1, expand=True)
    df['Playoff Year'] = df['Year'].astype(int)

    # Filter by year
    df = df.loc[(df['Playoff Year'] >= start_year) & (df['Playoff Year'] <= end_year)]

    # Clean winners and losers columns
    df[['Won_', 'Lost_']] = df['Unnamed: 2'].str.replace('*', '', regex=True).str.split('vs.', 1, expand=True)
    df['Won'] = df['Won_'].str.split('(', expand=True)[0].str.strip()
    df['Lost'] = df['Lost_'].str.split('(', expand=True)[0].str.strip()

    # Convert wide dataframe to long
    playoff_df = pd.melt(df,
                         id_vars=['Playoff Year', 'Playoff Series'],
                         var_name='Result',
                         value_name='Team',
                         value_vars=['Won', 'Lost'])
    return playoff_df


def get_season_data(start_year, end_year, postseason_data):
    driver = webdriver.Chrome(ChromeDriverManager().install())
    frames = []
    for y in range(start_year, end_year + 1):
        print('Retrieving {} Season Data...'.format(y))
        season_url = slug + '/leagues/majors/{0}-standings.shtml'.format(y)
        driver.get(season_url)
        time.sleep(2)
        print('Parsing Team List...')
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        standings_table = soup.find_all('table')[-1]
        team_names = [x.find('a').text for x in standings_table.find_all('tr')[1:-1]]
        team_links = [x.find('a').get('href') for x in standings_table.find_all('tr')[1:-1]]
        team_abv = [x.split('/')[2] for x in team_links]
        for t in range(len(team_names)):
            print('Team: {}'.format(team_names[t]))
            url = 'https://www.baseball-reference.com/teams/{0}/{1}-schedule-scores.shtml'.format(team_abv[t], y)
            data = pd.read_html(url)[0]
            data = data.loc[data['Gm#'] != 'Gm#']
            dates = [x[1].replace(' (1)', '').replace(' (2)', '') + ', ' + str(y) for x in data['Date'].str.split(',')]
            data['Team'] = team_names[t]
            data['Team Abv'] = team_abv[t]
            data['Game Date'] = pd.to_datetime(dates)
            data['Month'] = data['Game Date'].dt.month
            data['Year'] = data['Game Date'].dt.year
            data[['W', 'L']] = data['W-L'].str.split('-', 1, expand=True)
            data['W'] = data['W'].astype(int)
            data['L'] = data['L'].astype(int)
            data[['Postseason', 'National League Pennant', 'American League Pennant', 'World Series Champions']] = 0.0
            if postseason_data[postseason_data['Playoff Year'] == y]['Team'].str.contains(data['Team'][0]).any():
                data['Postseason'] = 1.0
            if postseason_data[(postseason_data['Playoff Year'] == y) &
                               (postseason_data['Playoff Series'] == 'World Series') &
                               (postseason_data['Result'] == 'Won')]['Team'].str.contains(data['Team'][0]).any():
                data['World Series Champions'] = 1.0
            if postseason_data[(postseason_data['Playoff Year'] == y) &
                               (postseason_data['Playoff Series'] == 'NLCS') &
                               (postseason_data['Result'] == 'Won')]['Team'].str.contains(data['Team'][0]).any():
                data['National League Pennant'] = 1.0
            if postseason_data[(postseason_data['Playoff Year'] == y) &
                               (postseason_data['Playoff Series'] == 'ALCS') &
                               (postseason_data['Result'] == 'Won')]['Team'].str.contains(data['Team'][0]).any():
                data['American League Pennant'] = 1.0
            frames.append(data)
            print('Appending Frames!')
            time.sleep(uniform(1, 3))
    driver.close()
    final_df = pd.concat(frames, ignore_index=True)
    return final_df


if __name__ == '__main__':
    starting_year = 2005
    ending_year = 2021
    slug = 'https://www.baseball-reference.com'

    dff = pd.read_csv('output/mlb_standings_1996_to_2021.csv', index_col=0, parse_dates=True)
    dff = dff.loc[dff['Year'] != 2020]
    playoff_data = get_playoff_data(starting_year, ending_year)
    playoff_data = playoff_data.loc[playoff_data['Playoff Year'] != 2020]
    dff.loc[dff['R'] > dff['RA'], 'Win_'] = 1
    april_df = dff.loc[dff.Month == 4]
    april_pivot = pd.pivot_table(april_df,
                                 index=['Year', 'Team'],
                                 values=['Win_',
                                         'W',
                                         'Postseason',
                                         'World Series Champions',
                                         'National League Pennant',
                                         'American League Pennant'],
                                 aggfunc={'Win_': sum,
                                          'W': 'count',
                                          'Postseason': 'last',
                                          'World Series Champions': 'last',
                                          'National League Pennant': 'last',
                                          'American League Pennant': 'last'})
    final_pivot = april_pivot.reset_index()
    final_pivot['Win Pct'] = final_pivot['Win_'] / final_pivot['W']
    total_playoff_team_pivot = pd.pivot_table(playoff_data, index=['Playoff Year'], values=['Team'],
                                              aggfunc=pd.Series.nunique)
    total_playoff_teams = total_playoff_team_pivot.sum()
    pivot_merged = playoff_data.merge(final_pivot, left_on=['Playoff Year', 'Team'], right_on=['Year', 'Team'],
                                      how='left')
    playoff_winners = pivot_merged.loc[(pivot_merged['Win Pct'] < 0.5) & (pivot_merged['Result'] == 'Won')][
        'Team'].nunique()
    # final_pivot['Win Pct'] = final_pivot['W'] / final_pivot['GP']
    # playoff_data = get_playoff_data(starting_year, ending_year)

    # file_name = 'output/mlb_standings_{0}_to_{1}.csv'.format(starting_year, ending_year)
