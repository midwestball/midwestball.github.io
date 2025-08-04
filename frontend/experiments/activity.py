from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
import time
import re
from datetime import datetime, timedelta
import json
import random
import requests

class XActivityScraper:
    def __init__(self, headless = True, delay_range = (2, 5)):
        self.delay_range = delay_range
        self.request_count = 0
        self.start_time = time.time()
        self.setup_driver(headless)
        self.activity_metrics = {}
    
    def setup_driver(self, headless):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        
        # Enhanced stealth options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins-discovery")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--start-maximized")
        
        # Random user agent rotation
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Additional prefs for stealth
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 2  # Don't load images for speed
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(options = chrome_options)
        
        # Execute stealth scripts
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                window.chrome = {runtime: {}};
            """
        })
        
        self.wait = WebDriverWait(self.driver, 15)
        self.actions = ActionChains(self.driver)
    
    def smart_delay(self, base_delay = None):
        """Implements intelligent delays with randomization and rate limiting"""
        if base_delay is None:
            delay = random.uniform(*self.delay_range)
        else:
            # Add randomization to base delay
            delay = base_delay + random.uniform(-0.5, 1.0)
        
        # Increase delay if we're making too many requests
        self.request_count += 1
        if self.request_count > 20:
            delay *= 1.5
        if self.request_count > 50:
            delay *= 2.0
        
        # Implement exponential backoff if we're going too fast
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0 and self.request_count / elapsed_time > 2:  # More than 2 requests per second
            delay *= 2.0
            
        time.sleep(max(delay, 1.0))  # Minimum 1 second delay
    
    def human_like_scroll(self, pixels = None):
        """Scrolls in a more human-like manner"""
        if pixels is None:
            pixels = random.randint(300, 800)
        
        current_position = self.driver.execute_script("return window.pageYOffset;")
        target_position = current_position + pixels
        
        # Scroll in chunks to simulate human behavior
        chunk_size = random.randint(50, 150)
        while current_position < target_position:
            next_position = min(current_position + chunk_size, target_position)
            self.driver.execute_script(f"window.scrollTo(0, {next_position});")
            current_position = next_position
            time.sleep(random.uniform(0.1, 0.3))
        
        self.smart_delay(1)
    
    def human_like_click(self, element):
        """Performs more human-like clicking with mouse movement"""
        try:
            # Move to element first, then click
            self.actions.move_to_element(element).pause(random.uniform(0.1, 0.5)).click().perform()
            self.smart_delay()
        except Exception as e:
            # Fallback to regular click
            element.click()
            self.smart_delay()
    def login_to_x(self, username, password):
        try:
            print("Navigating to X.com login...")
            self.driver.get("https://x.com/login")
            self.smart_delay(3)
            
            username_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='username']"))
            )
            
            # Type username character by character for human-like behavior
            for char in username:
                username_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            self.smart_delay(1)
            
            next_button = self.driver.find_element(By.XPATH, "//span[text()='Next']")
            self.human_like_click(next_button)
            
            password_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
            )
            
            # Type password character by character
            for char in password:
                password_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            self.smart_delay(1)
            
            login_button = self.driver.find_element(By.XPATH, "//span[text()='Log in']")
            self.human_like_click(login_button)
            
            # Wait for successful login with longer timeout
            self.wait.until(EC.url_contains("home"))
            print("Successfully logged in to X.com")
            self.smart_delay(3)
            return True
            
        except Exception as e:
            print(f"Login failed: {str(e)}")
            return False
    
    def navigate_to_profile(self, username):
        profile_url = f"https://x.com/{username}"
        print(f"Navigating to profile: {profile_url}")
        self.driver.get(profile_url)
        self.smart_delay(3)
        
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='UserName']")))
            print(f"Successfully loaded profile for @{username}")
            return True
        except TimeoutException:
            print(f"Could not load profile for {username}")
            return False
    
    def extract_profile_stats(self):
        stats = {}
        
        try:
            following_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/following')]//span")
            stats["following"] = self.parse_number(following_element.text.split()[0])
        except NoSuchElementException:
            stats["following"] = 0
        
        try:
            followers_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/verified_followers') or contains(@href, '/followers')]//span")
            stats["followers"] = self.parse_number(followers_element.text.split()[0])
        except NoSuchElementException:
            stats["followers"] = 0
        
        try:
            join_date_element = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='UserJoinDate']")
            join_text = join_date_element.get_attribute("title") or join_date_element.text
            stats["join_date"] = join_text
            stats["account_age_days"] = self.calculate_account_age(join_text)
        except NoSuchElementException:
            stats["join_date"] = "Unknown"
            stats["account_age_days"] = None
        
        return stats
    
    def analyze_recent_tweets(self, max_tweets = 20):
        tweet_data = []
        tweets_analyzed = 0
        scroll_attempts = 0
        max_scrolls = 8  # Reduced to be more conservative
        consecutive_no_new_tweets = 0
        
        print(f"Starting to analyze recent tweets (max: {max_tweets})...")
        
        while tweets_analyzed < max_tweets and scroll_attempts < max_scrolls:
            current_tweets = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='tweet']")
            new_tweets_found = False
            
            for tweet in current_tweets[tweets_analyzed:]:
                if tweets_analyzed >= max_tweets:
                    break
                
                tweet_info = self.extract_tweet_data(tweet)
                if tweet_info and tweet_info not in tweet_data:  # Avoid duplicates
                    tweet_data.append(tweet_info)
                    tweets_analyzed += 1
                    new_tweets_found = True
                    print(f"Analyzed tweet {tweets_analyzed}/{max_tweets}")
            
            if not new_tweets_found:
                consecutive_no_new_tweets += 1
                if consecutive_no_new_tweets >= 3:  # Stop if we're not finding new tweets
                    print("No new tweets found after multiple scrolls, stopping...")
                    break
            else:
                consecutive_no_new_tweets = 0
            
            if tweets_analyzed < max_tweets:
                print(f"Scrolling to load more tweets... (attempt {scroll_attempts + 1}/{max_scrolls})")
                self.human_like_scroll()
                scroll_attempts += 1
                
                # Longer delay after scrolling to let content load
                self.smart_delay(3)
        
        print(f"Finished analyzing {len(tweet_data)} tweets")
        return tweet_data
    
    def extract_tweet_data(self, tweet_element):
        try:
            tweet_data = {}
            
            try:
                time_element = tweet_element.find_element(By.CSS_SELECTOR, "time")
                tweet_data["timestamp"] = time_element.get_attribute("datetime")
                tweet_data["relative_time"] = time_element.text
            except NoSuchElementException:
                return None
            
            try:
                text_element = tweet_element.find_element(By.CSS_SELECTOR, "[data-testid='tweetText']")
                tweet_data["text"] = text_element.text
                tweet_data["is_reply"] = "Replying to" in tweet_element.text
            except NoSuchElementException:
                tweet_data["text"] = ""
                tweet_data["is_reply"] = False
            
            engagement_metrics = ["reply", "retweet", "like", "bookmark"]
            for metric in engagement_metrics:
                try:
                    metric_element = tweet_element.find_element(By.CSS_SELECTOR, f"[data-testid='{metric}']")
                    count_text = metric_element.get_attribute("aria-label") or "0"
                    tweet_data[f"{metric}_count"] = self.extract_count_from_aria_label(count_text)
                except NoSuchElementException:
                    tweet_data[f"{metric}_count"] = 0
            
            return tweet_data
            
        except Exception as e:
            print(f"Error extracting tweet data: {str(e)}")
            return None
    
    def calculate_activity_score(self, profile_stats, tweet_data):
        if not tweet_data:
            return {"activity_score": 0, "activity_level": "Inactive", "metrics": {}}
        
        recent_tweets = len(tweet_data)
        
        now = datetime.now()
        recent_tweet_count_7d = 0
        recent_tweet_count_24h = 0
        total_engagement = 0
        reply_count = 0
        
        for tweet in tweet_data:
            if tweet.get("timestamp"):
                tweet_time = datetime.fromisoformat(tweet["timestamp"].replace("Z", "+00:00"))
                time_diff = now - tweet_time.replace(tzinfo = None)
                
                if time_diff <= timedelta(days = 7):
                    recent_tweet_count_7d += 1
                if time_diff <= timedelta(hours = 24):
                    recent_tweet_count_24h += 1
            
            total_engagement += (
                tweet.get("like_count", 0) + 
                tweet.get("retweet_count", 0) + 
                tweet.get("reply_count", 0)
            )
            
            if tweet.get("is_reply", False):
                reply_count += 1
        
        avg_engagement = total_engagement / recent_tweets if recent_tweets > 0 else 0
        reply_ratio = reply_count / recent_tweets if recent_tweets > 0 else 0
        
        followers = profile_stats.get("followers", 0)
        engagement_rate = (avg_engagement / followers * 100) if followers > 0 else 0
        
        activity_score = (
            recent_tweet_count_7d * 2 +
            recent_tweet_count_24h * 5 +
            min(engagement_rate, 10) * 3 +
            reply_ratio * 10 +
            min(recent_tweets / 20, 1) * 15
        )
        
        if activity_score >= 50:
            activity_level = "Very Active"
        elif activity_score >= 30:
            activity_level = "Active"
        elif activity_score >= 15:
            activity_level = "Moderately Active"
        elif activity_score >= 5:
            activity_level = "Low Activity"
        else:
            activity_level = "Inactive"
        
        metrics = {
            "total_recent_tweets": recent_tweets,
            "tweets_last_7_days": recent_tweet_count_7d,
            "tweets_last_24_hours": recent_tweet_count_24h,
            "average_engagement": round(avg_engagement, 2),
            "engagement_rate_percent": round(engagement_rate, 4),
            "reply_ratio": round(reply_ratio, 3),
            "activity_score": round(activity_score, 2)
        }
        
        return {
            "activity_score": round(activity_score, 2),
            "activity_level": activity_level,
            "metrics": metrics
        }
    
    def parse_number(self, text):
        text = text.replace(",", "").replace("K", "000").replace("M", "000000")
        try:
            return int(float(text))
        except ValueError:
            return 0
    
    def extract_count_from_aria_label(self, aria_label):
        numbers = re.findall(r"\d+", aria_label)
        if numbers:
            return int(numbers[0])
        return 0
    
    def calculate_account_age(self, join_date_text):
        try:
            join_date = datetime.strptime(join_date_text, "%B %Y")
            return (datetime.now() - join_date).days
        except ValueError:
            try:
                join_date = datetime.strptime(join_date_text, "%B %d, %Y")
                return (datetime.now() - join_date).days
            except ValueError:
                return None
    
    def analyze_multiple_users(self, usernames, login_username = None, login_password = None):
        """
        Analyzes multiple users and returns a dictionary with their stats
        
        Args:
            usernames: List of usernames to analyze (without @)
            login_username: Optional login username
            login_password: Optional login password
            
        Returns:
            Dictionary where keys are usernames and values are lists with:
            [activity_level, activity_score, followers, following, account_age_days, 
             tweets_last_7_days, tweets_last_24_hours, engagement_rate, reply_ratio]
        """
        results = {}
        
        try:
            # Login once if credentials provided
            if login_username and login_password:
                if not self.login_to_x(login_username, login_password):
                    print("Login failed, proceeding without authentication")
            
            total_users = len(usernames)
            print(f"Starting analysis of {total_users} users...")
            
            for i, username in enumerate(usernames, 1):
                print(f"\n[{i}/{total_users}] Analyzing @{username}...")
                
                try:
                    if not self.navigate_to_profile(username):
                        print(f"Could not access profile for @{username}")
                        results[username] = self._get_empty_stats()
                        continue
                    
                    # Extract data
                    profile_stats = self.extract_profile_stats()
                    tweet_data = self.analyze_recent_tweets()
                    activity_analysis = self.calculate_activity_score(profile_stats, tweet_data)
                    
                    # Format results as list
                    stats_list = [
                        activity_analysis["activity_level"],
                        activity_analysis["activity_score"],
                        profile_stats.get("followers", 0),
                        profile_stats.get("following", 0),
                        profile_stats.get("account_age_days", 0),
                        activity_analysis["metrics"]["tweets_last_7_days"],
                        activity_analysis["metrics"]["tweets_last_24_hours"],
                        activity_analysis["metrics"]["engagement_rate_percent"],
                        activity_analysis["metrics"]["reply_ratio"]
                    ]
                    
                    results[username] = stats_list
                    print(f"✓ @{username}: {activity_analysis['activity_level']} (Score: {activity_analysis['activity_score']:.1f})")
                    
                    # Extra delay between users to be respectful
                    if i < total_users:
                        self.smart_delay(5)
                        
                except Exception as e:
                    print(f"Error analyzing @{username}: {str(e)}")
                    results[username] = self._get_empty_stats()
                    continue
            
            print(f"\n✓ Completed analysis of {total_users} users")
            return results
            
        except Exception as e:
            print(f"Error in batch analysis: {str(e)}")
            return results
    
    def _get_empty_stats(self):
        """Returns empty stats list for failed analyses"""
        return ["Unavailable", 0, 0, 0, 0, 0, 0, 0.0, 0.0]
    def analyze_user_activity(self, target_username, login_username = None, login_password = None):
        try:
            if login_username and login_password:
                if not self.login_to_x(login_username, login_password):
                    return None
            
            if not self.navigate_to_profile(target_username):
                return None
            
            print(f"Analyzing activity for @{target_username}...")
            
            profile_stats = self.extract_profile_stats()
            print(f"Profile stats extracted: {profile_stats}")
            
            tweet_data = self.analyze_recent_tweets()
            print(f"Analyzed {len(tweet_data)} recent tweets")
            
            activity_analysis = self.calculate_activity_score(profile_stats, tweet_data)
            
            result = {
                "username": target_username,
                "profile_stats": profile_stats,
                "activity_analysis": activity_analysis,
                "analyzed_at": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            print(f"Error analyzing user activity: {str(e)}")
            return None
    
    def get_user_stats_list(self, usernames, login_username = None, login_password = None):
        """
        Main function to analyze multiple Twitter users and return formatted results
        
        Args:
            usernames: List of Twitter handles (with or without @)
            login_username: Optional Twitter login username
            login_password: Optional Twitter login password
            
        Returns:
            Dictionary where:
            - Keys: Twitter handles (cleaned, without @)
            - Values: List with [activity_level, activity_score, followers, following, 
                     account_age_days, tweets_last_7_days, tweets_last_24_hours, 
                     engagement_rate_percent, reply_ratio]
        """
        # Clean usernames (remove @ if present)
        cleaned_usernames = [username.lstrip("@") for username in usernames]
        
        return self.analyze_multiple_users(cleaned_usernames, login_username, login_password)
    
    def close(self):
        if self.driver:
            self.driver.quit()

def analyze_twitter_users(usernames, login_username = None, login_password = None, headless = True):
    """
    Convenience function to analyze multiple Twitter users
    
    Args:
        usernames: List of Twitter handles (with or without @)
        login_username: Optional Twitter login username  
        login_password: Optional Twitter login password
        headless: Whether to run browser in headless mode (default True)
        
    Returns:
        Dictionary where keys are handles and values are lists with:
        [activity_level, activity_score, followers, following, account_age_days,
         tweets_last_7_days, tweets_last_24_hours, engagement_rate_percent, reply_ratio]
         
    Example:
        handles = ["elonmusk", "sundarpichai", "satyanadella"]
        results = analyze_twitter_users(handles)
        
        # Access results:
        # results["elonmusk"][0] = activity_level
        # results["elonmusk"][1] = activity_score  
        # results["elonmusk"][2] = followers
        # etc.
    """
    scraper = XActivityScraper(headless = headless, delay_range = (3, 7))
    
    try:
        results = scraper.get_user_stats_list(usernames, login_username, login_password)
        return results
    except Exception as e:
        print(f"Error in analysis: {str(e)}")
        return {}
    finally:
        scraper.close()

def main():
    # More conservative default settings
    scraper = XActivityScraper(headless = False, delay_range = (3, 7))
    
    try:
        print("X.com Activity Analyzer")
        print("=" * 30)
        print("1. Analyze single user")
        print("2. Analyze multiple users")
        choice = input("Choose option (1 or 2): ").strip()
        
        use_login = input("Do you want to log in? (y/n): ").lower() == "y"
        login_user, login_pass = None, None
        
        if use_login:
            login_user = input("Enter your X.com username/email: ")
            login_pass = input("Enter your X.com password: ")
        
        if choice == "2":
            print("\nEnter usernames separated by commas (e.g., elonmusk, sundarpichai, satyanadella)")
            usernames_input = input("Usernames: ")
            usernames = [u.strip().lstrip("@") for u in usernames_input.split(",")]
            
            results = scraper.get_user_stats_list(usernames, login_user, login_pass)
            
            if results:
                print("\n" + "=" * 80)
                print("BATCH ANALYSIS RESULTS")
                print("=" * 80)
                print(f"{'Username':<20} {'Activity':<15} {'Score':<8} {'Followers':<12} {'Following':<12}")
                print("-" * 80)
                
                for username, stats in results.items():
                    activity_level, score, followers, following = stats[0], stats[1], stats[2], stats[3]
                    print(f"@{username:<19} {activity_level:<15} {score:<8.1f} {followers:<12,} {following:<12,}")
                
                save_result = input("\nSave results to JSON file? (y/n): ").lower() == "y"
                if save_result:
                    filename = "batch_twitter_analysis.json"
                    formatted_results = {
                        username: {
                            "activity_level": stats[0],
                            "activity_score": stats[1], 
                            "followers": stats[2],
                            "following": stats[3],
                            "account_age_days": stats[4],
                            "tweets_last_7_days": stats[5],
                            "tweets_last_24_hours": stats[6],
                            "engagement_rate_percent": stats[7],
                            "reply_ratio": stats[8]
                        }
                        for username, stats in results.items()
                    }
                    
                    with open(filename, "w") as f:
                        json.dump(formatted_results, f, indent = 2)
                    print(f"Results saved to {filename}")
            else:
                print("No results to display")
        
        else:
            # Single user analysis (original functionality)
            target_user = input("Enter the X.com username to analyze (without @): ")
            
            if not use_login:
                print("Note: Without login, some data may be limited or unavailable")
            
            result = scraper.analyze_user_activity(target_user, login_user, login_pass)
            
            if result:
                print("\n" + "=" * 50)
                print(f"ACTIVITY ANALYSIS FOR @{result['username']}")
                print("=" * 50)
                
                profile = result["profile_stats"]
                print(f"Followers: {profile.get('followers', 'N/A'):,}")
                print(f"Following: {profile.get('following', 'N/A'):,}")
                print(f"Account Age: {profile.get('account_age_days', 'N/A')} days")
                
                activity = result["activity_analysis"]
                print(f"\nActivity Level: {activity['activity_level']}")
                print(f"Activity Score: {activity['activity_score']}/100")
                
                metrics = activity["metrics"]
                print(f"\nDetailed Metrics:")
                print(f"  Recent tweets analyzed: {metrics['total_recent_tweets']}")
                print(f"  Tweets in last 7 days: {metrics['tweets_last_7_days']}")
                print(f"  Tweets in last 24 hours: {metrics['tweets_last_24_hours']}")
                print(f"  Average engagement per tweet: {metrics['average_engagement']}")
                print(f"  Engagement rate: {metrics['engagement_rate_percent']}%")
                print(f"  Reply ratio: {metrics['reply_ratio']}")
                
                save_result = input("\nSave results to JSON file? (y/n): ").lower() == "y"
                if save_result:
                    filename = f"{target_user}_activity_analysis.json"
                    with open(filename, "w") as f:
                        json.dump(result, f, indent = 2)
                    print(f"Results saved to {filename}")
            
            else:
                print("Failed to analyze user activity")
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        print("Closing browser...")
        scraper.close()

if __name__ == "__main__":
    main()